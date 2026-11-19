#!/usr/bin/env python3
"""Compare empty-hand stop, mining, and Wrench rotation of running Clockwork Bearings."""

import argparse
import csv
from importlib import import_module
from itertools import groupby
from pathlib import Path
import re
import struct

from fixture_world import ROOT, fixture_world

windmill = import_module("test-windmill")
RIGS = ((8, 180, 23), (17, 180, 33), (8, 180, 43))


def geometry(rig):
    x, y, z = RIGS[rig]
    sign = -1 if rig == 1 else 1
    return (
        (x, y, z), (x - sign, y, z),
        "west" if sign < 0 else "east",
        [(x + sign * arm, y + height, z) for arm in (1, 2) for height in (0, 1)],
    )


def setup(control):
    commands = ["/gamerule minecraft:advance_time false", "/time set 2580",
                "/fill 4 179 18 22 179 47 minecraft:smooth_stone"]
    for rig in range(3):
        pos, _, face, cells = geometry(rig)
        commands.append(f"/setblock {windmill.coords(pos)} create:clockwork_bearing[facing={face}]")
        for i, (x, y, z) in enumerate(cells):
            material = "oak_planks" if i < 2 else "stone"
            commands.append(f"/setblock {x} {y} {z} minecraft:{material}")
            if i % 2 == 0:
                commands.append(f"/summon minecraft:marker {x} {y} {z} "
                                "{CreateSuperGlue:1b,From:[0d,0d,0d],To:[1d,2d,1d]}")
    control.commands(commands)


def action(control, obstruction):
    for rig, (x, y, z) in enumerate(RIGS):
        control.command(f"/tp @s {x + 0.5} {float(y)} {z - 2.5}")
        control.call("wait", 4)
        if obstruction and rig in (1, 2):
            cell = geometry(rig)[3][1]
            material = "iron_block" if rig == 1 else "bedrock"
            control.command(f"/setblock {windmill.coords(cell)} minecraft:{material}")
        if rig == 2:
            control.command("/item replace entity @s hotbar.0 with create:wrench 1")
            control.call("wait", 3)
            control.call("select", "create:wrench")
            control.call("interact", x, y, z, "up")
        else:
            control.call("look-at", x + 0.5, y + 0.91, z + 0.02)
            control.call("wait", 3)
            control.call("mouse", "left" if rig == 1 else "right", "click")
        control.call("wait", 3)


def sample(control, tick, rig, obstruction):
    pos, _, _, cells = geometry(rig)
    at = windmill.coords(pos)
    bearing, data, displays, *materials = control.commands((
        f"/execute if block {at} create:clockwork_bearing",
        f"/data get block {at}",
        f"/execute positioned {at} if entity @e[type=minecraft:block_display,distance=..3]",
        *(f"/execute if block {windmill.coords(cell)} minecraft:{'oak_planks' if i < 2 else 'stone'}"
          for i, cell in enumerate(cells)),
    ))
    face = "absent"
    if bearing.startswith("Test passed"):
        for direction in ("east", "west", "north", "south"):
            if control.command(f"/execute if block {at} create:clockwork_bearing[facing={direction}]").startswith("Test passed"):
                face = direction
                break
    shown = re.search(r"Count: (\d+)", displays)
    # Each contraption is represented by two individual block displays.
    count = int(shown[1]) if shown else 0
    if count % 2:
        raise RuntimeError(f"Clockwork rig {rig} has a partial hand at tick {tick}: {count} displays.")
    number = windmill.number
    fields = {"tick": tick, "rig": rig, "facing": face,
            "running": str(number(data, "Running") == 1).lower(),
            "present": sum(result.startswith("Test passed") for result in materials),
            "hands": count // 2,
            "hour_angle": number(data, "HourAngle"), "minute_angle": number(data, "MinuteAngle")}
    if obstruction:
        cell = windmill.coords(cells[1])
        for candidate in ("air", "oak_planks", "bedrock", "iron_block"):
            if control.command(f"/execute if block {cell} minecraft:{candidate}").startswith("Test passed"):
                fields["obstacle"] = f"minecraft:{candidate}"
                break
        else:
            fields["obstacle"] = "unknown"
        # Other fixture drops do not include either of these two resources.
        item = "iron_block" if rig == 1 else "oak_planks"
        drop = control.command(f"/execute positioned {at} run data get entity @e[type=minecraft:item,distance=..3,sort=nearest,limit=1] Item")
        fields["drops"] = int(number(drop, "count")) if f'minecraft:{item}' in drop else 0
    return fields


def run(args):
    errors = []
    trace = "clockwork-obstruction-java.csv" if args.obstruction else "clockwork-removal-java.csv"
    with (ROOT / "fixtures" / trace).open() as source:
        java = list(csv.DictReader(source))
    with fixture_world(args, "Clockwork-removal", render=True, pack=args.pack) as control:
        setup(control)
        start = control.clock()
        for tick, rows in groupby(java, key=lambda row: int(row["tick"])):
            if tick:
                control.step_to(start + tick)
            if tick == 1:
                for rig in range(3):
                    _, motor, face, _ = geometry(rig)
                    control.command(f"/setblock {windmill.coords(motor)} create:creative_motor[facing={face}]")
            if tick == 6:
                action(control, args.obstruction)
            for row in rows:
                actual = sample(control, tick, int(row["rig"]), args.obstruction)
                for key, value in actual.items():
                    want = row[key]
                    equal = (struct.pack(">f", value) == struct.pack(">f", float(want))
                             if key.endswith("_angle") else str(value) == want)
                    if not equal:
                        errors.append(f"{tick}/{row['rig']} {key}: Horizon {value}, Java {want}")
    if errors:
        raise RuntimeError(f"{len(errors)} Clockwork removal differences. " + "; ".join(errors[:25]))
    print(f"Matched all {len(java)} Java samples for empty-hand stop, mining, and Wrench rotation.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--obstruction", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
