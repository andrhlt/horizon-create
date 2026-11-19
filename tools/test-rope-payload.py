#!/usr/bin/env python3
"""Drive a glued chest and platform down and up in Java and Horizon."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/misc/threshold_switch_pulley.nbt")
X, Y, Z = 8, 112, -8
PULLEY = f"{X} {Y} {Z}"
MOTOR = f"{X + 1} {Y} {Z}"
KEYS = ("offset", "running", "payload_y", "rpm", "casing", "planks", "chest_copper")


def setup(control):
    control.commands((
        f"/setblock {PULLEY} create:rope_pulley[axis=x]",
        f"/setblock {MOTOR} create:creative_motor[facing=west]{{ScrollValue:0}}",
        f"/setblock {X} {Y - 1} {Z} create:andesite_casing",
        f"/setblock {X + 1} {Y - 1} {Z} minecraft:oak_planks",
        f'/setblock {X + 2} {Y - 1} {Z} minecraft:chest{{Items:[{{Slot:0b,count:7,id:"minecraft:copper_ingot"}}]}}',
        f"/fill {X - 1} {Y - 3} {Z - 4} {X + 4} {Y - 3} {Z - 1} minecraft:smooth_stone",
        "/gamemode survival",
        "/item replace entity @s hotbar.0 with create:super_glue",
    ))
    control.call("key", "1", "tap")
    for x in (X, X + 2):
        control.command(f"/tp @s {x + 0.5} {Y - 2} {Z - 1.8} 0 20")
        control.call("wait", 3)
        control.call("look-at", x + 0.5, Y - 0.55, Z + 0.5)
        control.call("mouse", "right", "click")
        control.call("wait", 3)
    item = control.command("/data get entity @s Inventory")
    if '"minecraft:damage": 2' not in item:
        raise RuntimeError(f"Glue did not connect the payload: {item}")


def scalar(nbt, key):
    found = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", nbt)
    return float(found[1]) if found else 0.0


def sample(control):
    data = control.command(f"/data get block {PULLEY}")
    offset = scalar(data, "Offset")
    y = Y - int(offset + 0.5) - 1
    a, b, chest, marker = control.commands((
        f"/execute if block {X} {y} {Z} create:andesite_casing",
        f"/execute if block {X + 1} {y} {Z} minecraft:oak_planks",
        f"/data get block {X + 2} {y} {Z} Items",
        "/data get entity @e[type=minecraft:marker,tag=create_rope_load,limit=1] Pos[1]",
    ))
    cargo = re.search(r"\bcount: (\d+)", chest)
    at = re.search(r"(-?\d+(?:\.\d+)?)d$", marker)
    return (
        offset,
        "true" if scalar(data, "Running") == 1.0 else "false",
        float(at[1]) - Y if at else 999.0,
        scalar(data, "Speed"),
        int("Test passed" in a),
        int("Test passed" in b),
        int(cargo[1]) if cargo else 0,
    )


def run(args):
    with (ROOT / "fixtures/rope_payload-java.csv").open() as data:
        expected = tuple(csv.DictReader(data))
    with fixture_world(args, "Rope-payload", STRUCTURE, render=args.visual) as control:
        setup(control)
        start = control.clock()
        first_difference = None
        with (ROOT / ".local/rope_payload-horizon.csv").open("w") as out:
            writer = csv.writer(out)
            writer.writerow(("tick", *KEYS))
            for row in expected:
                tick = int(row["tick"])
                if tick:
                    control.step_to(start + tick)
                values = sample(control)
                writer.writerow((tick, *values))
                want = tuple(row[key] if key == "running" else float(row[key]) for key in KEYS)
                if values != want:
                    difference = f"Tick {tick}: Horizon {values}, Java {want}"
                    if not args.diagnostics:
                        raise RuntimeError(difference)
                    first_difference = first_difference or difference
                if tick in (3, 24, 32, 56):
                    rpm = {3: -128, 24: 0, 32: 128, 56: 0}[tick]
                    control.command(f"/data merge block {MOTOR} {{ScrollValue:{rpm}}}")
                if args.visual and tick == 18:
                    control.commands(("/time set noon", "/setblock 12 112 -3 minecraft:smooth_stone", "/tp @s 12.3 113.0 -3.0"))
                    control.call("wait", 3)
                    control.call("look-at", 9, 109, -7.5)
                    control.call("key", "f1", "tap")
                    control.call("wait", 4)
                    control.call("screenshot", ROOT / ".local/rope-payload.png")
                    control.call("key", "f1", "tap")
        if first_difference:
            raise RuntimeError(first_difference)
        drops = control.command("/execute if entity @e[type=minecraft:item]")
        if "Test passed" in drops:
            raise RuntimeError(control.command("/data get entity @e[type=minecraft:item,limit=1] Item"))
    print(f"Rope Pulley motion, its platform, and copper cargo matched all {len(expected)} Java ticks.")


def detach(args):
    with fixture_world(args, "Rope-detach", STRUCTURE, render=args.visual) as control:
        setup(control)
        start = control.clock()
        control.command(f"/data merge block {MOTOR} {{ScrollValue:-128}}")
        for tick in range(1, 13):
            control.step_to(start + tick)
            offset, running, moving, *_ = sample(control)
            if (offset, running, moving) == (1.5, "true", -2.5):
                break
        else:
            raise RuntimeError("The moving payload did not reach the half-block extension")
        control.command(f"/setblock {PULLEY} minecraft:air")
        control.step_to(start + tick + 1)
        y = Y - 3
        casing, planks, chest, marker = control.commands((
            f"/execute if block {X} {y} {Z} create:andesite_casing",
            f"/execute if block {X + 1} {y} {Z} minecraft:oak_planks",
            f"/data get block {X + 2} {y} {Z} Items",
            "/execute if entity @e[type=minecraft:marker,tag=create_rope_load]",
        ))
        if (casing, planks, marker) != ("Test passed", "Test passed", "Test failed"):
            raise RuntimeError(f"Detached load did not land at the Java height: {casing}, {planks}, {marker}")
        if 'count: 7' not in chest or 'minecraft:copper_ingot' not in chest:
            raise RuntimeError(f"Detached load lost cargo: {chest}")
    print("Removing the Rope Pulley at 1.5 blocks landed the payload 3 blocks below it with all seven copper ingots.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--detach", action="store_true")
    args = parser.parse_args()
    (detach if args.detach else run)(args)
