#!/usr/bin/env python3
"""Compare three Windmill Bearing layouts with pinned Java Create."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
import struct

from fixture_world import ROOT, fixture_world

SAILS = (7, 8, 16)
WINDMILLS = tuple((8, 180, 23 + rig * 7) for rig in range(len(SAILS)))
MATERIALS = ("white_sail", "sail_frame", "red_sail")
NUMBERS = ("generated_rpm", "bearing_rpm", "shaft_rpm", "angle", "stress", "capacity")


def coords(position):
    return " ".join(map(str, position))


def cells(bearing, sails):
    x, y, z = bearing
    return tuple((x + 1, y + cell // 4, z + cell % 4) for cell in range(sails))


def setup(control):
    control.commands((
        "/fill 5 179 20 13 179 42 minecraft:smooth_stone",
        "/fill 5 180 20 13 184 42 minecraft:air",
        "/gamemode survival",
        "/tp @s 8.5 180.0 21.5",
    ))
    for rig, (pos, sails) in enumerate(zip(WINDMILLS, SAILS, strict=True)):
        x, y, z = pos
        control.commands((
            f"/setblock {coords(pos)} create:windmill_bearing[facing=east]",
            f"/setblock {x - 1} {y} {z} create:shaft[axis=x]",
            f"/setblock {x - 2} {y} {z} create:encased_fan[facing=west]",
            *(f"/setblock {coords(at)} " + (
                "minecraft:white_wool" if rig == 2 and index == 15
                else f"create:{MATERIALS[index % len(MATERIALS)]}[facing=east]"
            ) for index, at in enumerate(cells(pos, sails))),
            f"/summon minecraft:marker {x + 1} {y} {z} "
            "{CreateSuperGlue:1b,From:[0d,0d,0d],To:[1d,4d,4d]}",
        ))


def operate(control):
    for pos in WINDMILLS:
        x, y, z = pos
        control.command(f"/tp @s {x + 0.5} {float(y)} {z - 2.5}")
        control.call("wait", 3)
        # Click above the centered value box, on the bearing's exposed housing.
        control.call("look-at", x + 0.5, y + 0.91, z + 0.02)
        control.call("wait", 2)
        control.call("mouse", "right", "click")
        control.call("wait", 2)


def aim_direction(control, pos, teleport):
    x, y, z = pos
    if teleport:
        control.command(f"/tp @s {x + 0.5} {float(y)} {z - 2.5}")
        control.call("wait", 3)
    control.call("look-at", x + 0.375, y + 0.5, z + 0.015)
    control.call("wait", 2)


def short_press(control, pos):
    aim_direction(control, pos, True)
    control.call("mouse", "right", "down")
    control.call("wait", 3)
    if control.call("state")["screen"] != "playing":
        raise RuntimeError("A three-tick press opened the Windmill direction setting")
    control.call("mouse", "right", "up")
    control.call("wait", 3)
    nbt = control.command(f"/data get block {coords(pos)}")
    if number(nbt, "Running") or number(nbt, "ScrollValue"):
        raise RuntimeError("A short press changed Windmill settings or started rotation")


def configure(control, pos, counterclockwise, *, teleport=True, capture=False):
    aim_direction(control, pos, teleport)
    control.call("mouse", "right", "down")
    control.call("wait", 7)
    selection = "Counter-Clockwise" if counterclockwise else "Clockwise"
    cell = next((button for button in control.call("screen")["buttons"] if button["label"] == selection), None)
    if cell is None:
        raise RuntimeError(f"The Windmill did not open its direction board at {pos}")
    pointer = (cell["x"] + cell["w"] / 2, cell["y"] + cell["h"] / 2)
    control.call("scroll-at", *pointer, 0)
    if capture:
        control.call("screenshot", ROOT / ".local/windmill-direction-board.png")
    control.call("click-at", *pointer, "right")
    control.call("wait", 3)
    if control.call("state")["screen"] != "playing":
        raise RuntimeError(f"The Windmill did not close its direction board at {pos}")


def verify_held_inputs(control, count):
    started = {}
    opens = releases = submissions = 0
    for line in (control.socket.parent / "ctl.log").read_text().splitlines():
        if not line.startswith("CREATE_SPEED_CONTROLLER_INPUT "):
            continue
        _, tick, event, pos = line.split()
        if event == "hold":
            started[pos] = int(tick)
        elif event == "open":
            if int(tick) - started[pos] + 1 != 6:
                raise RuntimeError(f"Windmill value board opened outside the sixth held client tick: {line}")
            opens += 1
        elif event == "release":
            releases += 1
        elif event == "submit":
            submissions += 1
    if (opens, releases, submissions) != (count,) * 3:
        raise RuntimeError(f"Expected {count} board opens, releases and submissions, got {opens}/{releases}/{submissions}")


def number(data, key):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", data)
    return float(match[1]) if match else 0.0


def observe(control, pos, sails, tick, rig):
    x, y, z = pos
    bearing, shaft, *present = control.commands((
        f"/data get block {coords(pos)}",
        f"/data get block {x - 1} {y} {z}",
        *(f"/execute if block {coords(at)} minecraft:air" for at in cells(pos, sails)),
    ))
    if "has the following block data" not in bearing:
        raise RuntimeError(f"Missing Windmill Bearing data at {pos}: {bearing}")
    return {
        "tick": tick, "rig": rig,
        "running": str(number(bearing, "Running") == 1).lower(),
        "generated_rpm": number(bearing, "LastGenerated"),
        "bearing_rpm": number(bearing, "Speed"),
        "shaft_rpm": number(shaft, "Speed"),
        "angle": number(bearing, "Angle"),
        "stress": number(bearing, "Stress"),
        "capacity": number(bearing, "Capacity"),
        "captured": int(number(bearing, "Sails")),
        "present": sum(not value.startswith("Test passed") for value in present),
        "assembly_error": str("NotEnoughSails:" in bearing).lower(),
    }


def compare(expected, actual):
    for key, value in expected.items():
        observed = actual[key]
        if key in NUMBERS:
            equal = struct.pack(">f", float(value)) == struct.pack(">f", observed)
        else:
            equal = value == str(observed)
        if not equal:
            raise RuntimeError(
                f"Tick {actual['tick']}, rig {actual['rig']}, {key}: Java {value}, Horizon {observed}. "
                f"Horizon row {actual}"
            )


def run(args):
    with (ROOT / "fixtures/windmill-java.csv").open() as file:
        expected = list(csv.DictReader(file))
    trace = ROOT / ".local/windmill-horizon.csv"
    with fixture_world(args, "Windmill", pack=args.pack, render=True,
                       env={"CREATE_SPEED_CONTROLLER_INPUT_TRACE": "1"}) as control, trace.open("w", newline="") as result:
        writer = csv.DictWriter(result, fieldnames=list(expected[0]), lineterminator="\n")
        writer.writeheader()
        setup(control)
        if args.board:
            short_press(control, WINDMILLS[1])
        start = control.clock()
        for tick in range(22):
            if tick:
                control.step_to(start + tick)
            if tick in (1, 18):
                operate(control)
            if tick in (9, 14):
                value = 1 if tick == 9 else 0
                if args.board:
                    for at in WINDMILLS:
                        configure(control, at, bool(value), capture=args.visual and tick == 9 and at == WINDMILLS[1])
                else:
                    control.commands(f"/data merge block {coords(at)} {{ScrollValue:{value}}}" for at in WINDMILLS)
            for rig, (pos, sails) in enumerate(zip(WINDMILLS, SAILS, strict=True)):
                row = observe(control, pos, sails, tick, rig)
                writer.writerow(row)
                compare(expected[tick * len(SAILS) + rig], row)
            if args.visual and tick in (8, 17):
                control.command("/tp @s 5.5 181.0 33.5")
                control.call("look-at", 9.4, 182, 39)
                control.call("key", "f1", "tap")
                control.call("wait", 5)
                control.call("screenshot", ROOT / f".local/windmill-{tick}.png")
                control.call("key", "f1", "tap")
        if args.board:
            verify_held_inputs(control, 2 * len(WINDMILLS))
    print(f"All {len(expected)} Java Windmill samples matched start, reversal, stress and restoration.")


def craft(args):
    recipes = (
        ("windmill_bearing", 1, (("minecraft:oak_slab", (101,)), ("minecraft:stone", (104,)),
                                 ("create:shaft", (107,)))),
        ("white_sail", 2, (("minecraft:white_wool", (100,)), ("minecraft:stick", (101, 103)),
                           ("create:andesite_alloy", (104,)))),
        ("sail_frame", 1, (("create:white_sail", (100,)),)),
        ("white_sail", 1, (("create:sail_frame", (100,)),)),
    )
    inventory = import_module("test-survival-crafting")
    with fixture_world(args, "Windmill-crafting", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 5 179 21 11 179 25 minecraft:smooth_stone",
            "/setblock 8 180 23 minecraft:crafting_table",
            "/tp @s 6.5 180.0 23.5",
            "/gamemode survival",
        ))
        for result, count, ingredients in recipes:
            control.command("/clear @s")
            control.commands(
                f"/item replace entity @s hotbar.{index} with {source} {len(slots)}"
                for index, (source, slots) in enumerate(ingredients)
            )
            control.call("wait", 3)
            control.call("interact", 8, 180, 23, "west")
            control.call("wait", 3)
            for index, (_, slots) in enumerate(ingredients):
                inventory.distribute(control, index, slots)
            inventory.craft(control, f"create:{result}", count)
            control.call("close")
    print("Survival crafting verified the original Windmill Bearing, sail, and both sail-frame conversions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--craft", action="store_true")
    parser.add_argument("--board", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    (craft if args.craft else run)(args)
