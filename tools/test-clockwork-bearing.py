#!/usr/bin/env python3
"""Replay two powered Clockwork Bearings against the original Java ticks."""

import argparse
import csv
from importlib import import_module
from itertools import groupby
from pathlib import Path
import struct
import re

from fixture_world import ROOT, fixture_world

windmill = import_module("test-windmill")
GEOMETRY = {"east": ((8, 180, 23), 1), "west": ((17, 180, 33), -1)}
NUMBER_KEYS = {
    "rpm": "Speed", "hour_angle": "HourAngle", "minute_angle": "MinuteAngle",
    "stress": "Stress", "capacity": "Capacity",
}


def parts(facing):
    (x, y, z), sign = GEOMETRY[facing]
    return (x, y, z), (x - sign, y, z), tuple(
        (x + sign * arm, y + height, z) for arm in (1, 2) for height in (0, 1)
    )


def setup(control):
    control.command("/setblock 8 180 23 create:clockwork_bearing")
    default = control.command("/execute if block 8 180 23 create:clockwork_bearing[facing=north]")
    if not default.startswith("Test passed"):
        raise RuntimeError(f"Clockwork Bearing's default state differs from Java: {default}")
    rule = control.command("/gamerule minecraft:advance_time false")
    if "false" not in rule:
        raise RuntimeError(f"Clockwork fixture could not freeze time of day: {rule}")
    commands = ["/time set 2580", "/fill 4 179 20 22 179 37 minecraft:smooth_stone",
                "/fill 5 180 21 20 184 35 minecraft:air", "/tp @s 10 180 28"]
    for face in GEOMETRY:
        pos, _, cells = parts(face)
        commands.append(f"/setblock {windmill.coords(pos)} create:clockwork_bearing[facing={face}]")
        for i, (x, y, z) in enumerate(cells):
            material = "oak_planks" if i < 2 else "stone"
            commands.append(f"/setblock {x} {y} {z} minecraft:{material}")
            if i % 2 == 0:
                commands.append(f"/summon minecraft:marker {x} {y} {z} "
                                "{CreateSuperGlue:1b,From:[0d,0d,0d],To:[1d,2d,1d]}")
    control.commands(commands)


def count_hand(hands):
    if "has the following block data:" not in hands:
        return 0
    return hands.split("has the following block data:", 1)[1].count("BlockState:")


def observe(control, facing, tick):
    pos, _, cells = parts(facing)
    at = windmill.coords(pos)
    data, hour, minute, *present = control.commands((
        f"/data get block {at}", f"/data get block {at} HourBlocks", f"/data get block {at} MinuteBlocks",
        *(f"/execute if block {windmill.coords(cell)} minecraft:air" for cell in cells),
    ))
    if "has the following block data:" not in data:
        raise RuntimeError(f"Missing Clockwork Bearing at {pos}: {data}")
    hand_fields = []
    for name, detail, distance in (
        ("HOUR", hour, 0), ("MINUTE", minute, int(windmill.number(data, "MinuteOffset"))),
    ):
        count = count_hand(detail)
        if count:
            hand_fields.append(f"{name}:{distance}:{count}")
    return {
        "tick": tick, "facing": facing, "running": str(windmill.number(data, "Running") == 1).lower(),
        **{key: windmill.number(data, field) for key, field in NUMBER_KEYS.items()},
        "present": sum(not result.startswith("Test passed") for result in present),
        "hands": "|".join(hand_fields),
    }


def run(args):
    trace = "clockwork-settling-java.csv" if args.settling else "clockwork-bearing-java.csv"
    with (ROOT / "fixtures" / trace).open() as source:
        java = list(csv.DictReader(source))
    errors = []
    with fixture_world(args, "Clockwork-bearing", render=args.visual, pack=args.pack) as control:
        setup(control)
        times = {0: 10, 18: 5000, 30: 16000} if args.settling else {14: 18335}
        modes = {18: 1, 30: 2} if args.settling else {8: 1, 14: 2}
        start = control.clock()
        for tick, expected in groupby(java, key=lambda row: int(row["tick"])):
            if tick:
                control.step_to(start + tick)
            if tick == 1:
                control.commands(f"/setblock {windmill.coords(parts(face)[1])} create:creative_motor[facing={face}]"
                                 for face in GEOMETRY)
            if tick == 2 and args.settling:
                control.commands(f"/data merge block {windmill.coords(parts(face)[1])} {{ScrollValue:256}}"
                                 for face in GEOMETRY)
            if tick in times:
                control.command(f"/time set {times[tick]}")
            if tick in modes:
                control.commands(f"/data merge block {windmill.coords(parts(face)[0])} {{ScrollValue:{modes[tick]}}}"
                                 for face in GEOMETRY)
            if tick == 18 and not args.settling:
                control.commands(f"/setblock {windmill.coords(parts(face)[1])} minecraft:air" for face in GEOMETRY)
            for row in expected:
                found = observe(control, row["facing"], tick)
                for key, got in found.items():
                    want = row[key]
                    equal = (struct.pack(">f", got) == struct.pack(">f", float(want))
                             if key in NUMBER_KEYS else str(got) == want)
                    if not equal:
                        errors.append(f"{tick}/{row['facing']} {key}: {got} vs {want}")
            if tick in (0, 3, 14, 18, 19):
                response = control.command("/execute if entity @e[type=minecraft:block_display]")
                match = re.search(r"Count: (\d+)", response)
                count = int(match[1]) if match else 0
                expected_displays = 8 if tick in (3, 14, 18) or (args.settling and tick == 19) else 0
                if count != expected_displays:
                    errors.append(f"{tick} block display count: {count} vs {expected_displays}")
            if args.visual and tick in (7, 17, 21):
                control.command("/tp @s 7.5 180 20.5")
                control.call("look-at", 9, 180.8, 23.5)
                control.call("wait", 3)
                control.call("screenshot", ROOT / f".local/clockwork-bearing-{tick}.png")
    if errors:
        raise RuntimeError(f"{len(errors)} Clockwork observations differ from Java. " + "; ".join(errors[:24]))
    print(f"Matched {len(java)} Java Clockwork samples across both hands, three modes, and power changes.")


def craft(args):
    inventory = import_module("test-survival-crafting")
    with fixture_world(args, "Clockwork-crafting", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 5 179 20 10 179 25 minecraft:smooth_stone",
            "/setblock 8 180 23 minecraft:crafting_table",
            "/tp @s 6.5 180 23.5", "/gamemode survival",
            "/item replace entity @s hotbar.0 with minecraft:oak_slab 1",
            "/item replace entity @s hotbar.1 with create:brass_casing 1",
            "/item replace entity @s hotbar.2 with create:electron_tube 1",
        ))
        control.call("wait", 3)
        control.call("interact", 8, 180, 23, "west")
        control.call("wait", 3)
        for slot, cell in enumerate((101, 104, 107)):
            inventory.distribute(control, slot, (cell,))
        inventory.craft(control, "create:clockwork_bearing", 1)
    print("Survival crafting matched the original Clockwork Bearing recipe.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--craft", action="store_true")
    parser.add_argument("--settling", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    (craft if args.craft else run)(args)
