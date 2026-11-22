#!/usr/bin/env python3
"""Assemble a glued carriage in Horizon and compare wheel positions on every tick."""

import argparse
import csv
import math
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/misc/threshold_switch_pulley.nbt")
X, Y, Z = 9, 112, -8
STATION = (X, Y, Z + 2)
ENTITY = "@e[type=minecraft:interaction,nbt={CreateTrain:{}},limit=1,sort=nearest]"
NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?"


def click_track(control, x):
    control.call("look-at", x + 0.5, Y + 0.06, Z + 0.5)
    control.call("mouse", "right", "click")
    control.call("wait", 3)


def setup(control, layout=None, *, after_station=None, station_discovery_ticks=0, before_glue=None,
          take_controls=True, rear_controls=False):
    if layout is None:
        control.commands((
            f"/fill {X - 21} {Y - 1} {Z - 5} {X + 25} {Y - 1} {Z + 5} minecraft:smooth_stone",
            f"/fill {X - 20} {Y} {Z} {X + 24} {Y} {Z} create:track[shape=xo]",
            "/gamemode survival",
        ))
    else:
        layout(control)
    control.commands((
        f"/tp @s {X + 2.5} {Y} {Z + 0.5} 90 20",
        "/item replace entity @s hotbar.0 with create:track_station",
    ))
    control.call("wait", 3)
    control.call("key", "1", "tap")
    click_track(control, X)
    sx, sy, sz = STATION
    control.command(f"/tp @s {sx + 0.5} {sy} {sz + 2.5} 180 20")
    control.call("wait", 3)
    control.call("interact", sx, sy - 1, sz, "up")
    control.step_to(control.clock() + 1)
    if after_station:
        after_station(control)
        control.command(f"/tp @s {sx + 0.5} {sy} {sz + 2.5} 180 20")
    for _ in range(station_discovery_ticks):
        control.step_to(control.clock() + 1)
    control.call("wait", 3)
    control.call("interact", *STATION, "up")
    control.call("wait", 4)
    control.call("click-button", "Create New Train")
    control.step_to(control.clock() + 1)
    if station_discovery_ticks:
        control.call("wait", 1)
        buttons = control.call("screen")["buttons"]
        assemble = next((button for button in buttons if button["label"] == "Assemble Train"), None)
        if not assemble:
            raise RuntimeError(f"Station did not open its assembly screen: {buttons}")
    control.call("key", "esc", "tap")
    control.command("/item replace entity @s hotbar.0 with create:railway_casing 2")
    control.call("wait", 3)
    for x in (X + 1, X + 4):
        control.command(f"/tp @s {x + 0.5} {Y} {Z - 1.6} 0 20")
        control.call("wait", 3)
        click_track(control, x)
        block = control.call("block", x, Y + 1, Z)["block"]
        if block != "create:small_bogey":
            raise RuntimeError(f"No bogey above {x}, read {block}")
    control.commands((
        f"/fill {X + 1} {Y + 2} {Z} {X + 4} {Y + 2} {Z} minecraft:oak_planks",
        f"/setblock {X + 1} {Y + 3} {Z} create:controls[facing=east]",
    ))
    if rear_controls:
        control.command(f"/setblock {X + 4} {Y + 3} {Z} create:controls[facing=west]")
    if before_glue:
        before_glue(control)
    control.command("/item replace entity @s hotbar.0 with create:super_glue")
    control.call("wait", 3)
    for x, y in ((X + 4, Y + 1), (X + 1, Y + 3)):
        control.command(f"/tp @s {x + 0.5} {min(Y+1.5,y-1.0)} {Z - 1.7} 0 0")
        control.call("wait", 3)
        control.call("look-at", x + 0.5, y + 0.45, Z + 0.5)
        control.call("mouse", "right", "click")
        control.call("wait", 3)
    inventory = control.command("/data get entity @s Inventory")
    if '"minecraft:damage": 2' not in inventory or "create:super_glue_start" in inventory:
        raise RuntimeError(f"Expected Java glue durability to be spent: {inventory}")
    control.call("key", "2", "tap")
    control.command(f"/tp @s {sx + 0.5} {sy} {sz + 2.5} 180 20")
    control.call("wait", 3)
    control.step_to(control.clock() + 1)
    control.call("interact", *STATION, "up")
    control.call("wait", 4)
    control.call("click-button", "Assemble Train")
    control.call("wait", 3)
    if "assembling=false" not in control.call("block", *STATION)["state"]:
        control.call("screenshot", ROOT / ".local/train-assembly-error.png")
        raise RuntimeError("The connected carriage did not assemble")
    control.call("key", "esc", "tap")
    control.step_to(control.clock() + 1)
    control.call("wait", 3)
    control.command("/attribute @s minecraft:movement_speed base set 0")
    control.command(f"/tp @s {X + 0.5} {Y} {Z - 1.3} -35 -20")
    control.call("wait", 3)
    if take_controls:
        control.call("look-at", X + 1.5, Y + 3.45, Z + 0.5)
        control.call("mouse", "right", "click")
        control.call("wait", 3)


def sample(control):
    speed, wheels, spacing = control.commands(f"/data get entity {ENTITY} CreateTrain.{key}"
                                               for key in ("Speed", "WheelPoints", "BogeySpacing"))
    floats = tuple(float(value) for value in re.findall(f"({NUMBER})d", wheels))
    if len(floats) != 4:
        raise RuntimeError(f"Failed to parse wheel positions from {wheels}")
    return float(re.search(f"({NUMBER})d$", speed)[1]), *floats, int(spacing.split()[-1])


def run(args):
    trace = "manual_train"
    with (ROOT / f"fixtures/{trace}-java.csv").open() as data:
        expected = tuple(csv.DictReader(data))
    keys = ("speed", "wheel_1", "wheel_2", "wheel_3", "wheel_4", "spacing")
    output = ROOT / f".local/{trace}-horizon.csv"
    with fixture_world(args, "Simple-train", STRUCTURE, render=True, pack=args.pack) as control, output.open("w") as log:
        setup(control)
        start = control.clock()
        original = control.call("blocks", X + 1, Y + 1, Z, X + 4, Y + 3, Z)["blocks"]
        original_count = sum(block[3] != "minecraft:air" for block in original)
        if original_count != int(expected[0]["original_blocks"]):
            raise RuntimeError(f"Assembly left {original_count} blocks behind: {original}")
        writer = csv.writer(log)
        writer.writerow(("tick", *keys))
        for row in expected:
            t = int(row["tick"])
            if t > int(expected[0]["tick"]):
                control.step_to(start + t - int(expected[0]["tick"]))
            found = sample(control)
            writer.writerow((t, *found))
            log.flush()
            for key, value in zip(keys, found, strict=True):
                if not math.isclose(value, float(row[key]), rel_tol=0.0, abs_tol=1.2e-6):
                    raise RuntimeError(f"Tick {t} {key}: Horizon {value}, Java {row[key]}")
            if t == 18:
                control.call("key", "w", "down")
                control.call("wait", 3)
            elif t == 49:
                control.call("key", "w", "up")
                control.call("wait", 3)
            elif t == 84:
                control.call("key", "s", "down")
                control.call("wait", 3)
            elif t == 110:
                control.call("key", "s", "up")
                control.call("wait", 3)
        if args.visual:
            control.command("/time set noon")
            control.command(f"/tp @s {X + 5.5} {Y + 4.5} {Z - 5.5} 20 20")
            control.call("wait", 4)
            control.call("look-at", X + 1.3, Y + 1.9, Z + 0.5)
            control.call("key", "f1", "tap")
            control.call("wait", 5)
            control.call("screenshot", ROOT / ".local/simple-train.png")
    print(f"Train assembly and motion matched Java for all {len(expected)} ticks.")


def disassembly(args):
    with fixture_world(args, "Train-disassembly", STRUCTURE, render=True, pack=args.pack) as control:
        setup(control)
        x, y, z = STATION
        control.command(f"/tp @s {x + 0.5} {y} {z + 2.5} 180 20")
        control.call("wait", 3)
        control.call("interact", *STATION, "up")
        control.call("wait", 4)
        control.call("click-button", "Disassemble Train")
        control.step_to(control.clock() + 1)
        control.call("wait", 3)
        placed = {
            (block[0], block[1], block[2]): block[3].split("[", 1)[0]
            for block in control.call("blocks", X + 1, Y + 1, Z, X + 4, Y + 3, Z)["blocks"]
            if block[3] != "minecraft:air"
        }
        expected = {
            (X + 1, Y + 1, Z): "create:small_bogey",
            (X + 4, Y + 1, Z): "create:small_bogey",
            (X + 1, Y + 3, Z): "create:controls",
            **{(i, Y + 2, Z): "minecraft:oak_planks" for i in range(X + 1, X + 5)},
        }
        if placed != expected:
            raise RuntimeError(f"Disassembly left {placed}, expected {expected}")
        if "assembling=true" not in control.call("block", *STATION)["state"]:
            raise RuntimeError("Station did not return to assembly mode")
        controls = control.call("block", X + 1, Y + 3, Z)["state"]
        if "facing=east" not in controls:
            raise RuntimeError(f"Disassembly changed controls orientation: {controls}")
        remaining = control.command(f"/data get entity {ENTITY} CreateTrain")
        if "Track:" in remaining or "BogeySpacing:" in remaining:
            raise RuntimeError(f"Disassembly left a live train: {remaining}")
    print("Station disassembly restored seven blocks, controls orientation, and assembly mode.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--disassemble", action="store_true")
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    (disassembly if args.disassemble else run)(args)


if __name__ == "__main__":
    main()
