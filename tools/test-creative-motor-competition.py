#!/usr/bin/env python3
"""Compare two Creative Motors sharing one shaft with pinned Java.

The pinned Java probe places, in two lanes, a motor, a shaft and a second motor
that share one axis. It records the existence and speed of all three blocks
while the second motor's setting is flipped, the first motor is removed and the
first motor is re-added. This replay reproduces the same lanes and compares every
sampled tick.
"""

import argparse
import csv
import re
from pathlib import Path

from fixture_world import ROOT, fixture_world

BASES = (10, 16)
Y = 101
Z = -10
TICKS = 24


def coords(pos):
    return " ".join(map(str, pos))


def setup(control):
    commands = [
        f"/fill 5 99 -13 22 104 -8 minecraft:air",
        f"/fill 5 99 -13 22 99 -8 minecraft:smooth_stone",
        "/tp @s 13 100 -5",
    ]
    for case, base in enumerate(BASES):
        commands.extend((
            f"/setblock {base} {Y} {Z} create:creative_motor[facing=east]",
            f"/setblock {base + 1} {Y} {Z} create:shaft[axis=x]",
            f"/setblock {base + 2} {Y} {Z} create:creative_motor[facing=west]",
            f"/data merge block {base} {Y} {Z} {{ScrollValue:16}}",
            f"/data merge block {base + 2} {Y} {Z} {{ScrollValue:{16 if case == 0 else -16}}}",
        ))
    control.commands(commands)


def speed(control, pos):
    nbt = control.command(f"/data get block {coords(pos)}")
    match = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)", nbt)
    return float(match[1]) if match else 0.0


def sample(control, tick):
    actual = []
    for case, base in enumerate(BASES):
        for offset in range(3):
            pos = (base + offset, Y, Z)
            present = 1 if control.call("block", *pos)["state"].startswith("create:") else 0
            actual.append((tick, case, offset, present, speed(control, pos) if present else 0.0))
    return actual


def verify(args):
    with (ROOT / "fixtures/creative-motor-competition-java.csv").open() as stream:
        expected = {
            (int(row["tick"]), int(row["case"]), int(row["offset"])): (int(row["present"]), float(row["speed"]))
            for row in csv.DictReader(stream)
        }
    with fixture_world(args, "CreativeMotorCompetition", pack=args.pack) as control:
        setup(control)
        start = control.clock()
        actual = {}
        for tick in range(1, TICKS + 1):
            if tick == 5:
                control.commands(
                    f"/data merge block {BASES[case] + 2} {Y} {Z} {{ScrollValue:{-16 if case == 0 else 16}}}"
                    for case in range(len(BASES))
                )
            if tick == 12:
                control.commands(f"/setblock {BASES[case]} {Y} {Z} minecraft:air" for case in range(len(BASES)))
            if tick == 18:
                control.commands(
                    f"/setblock {BASES[case]} {Y} {Z} create:creative_motor[facing=east]" for case in range(len(BASES))
                )
                control.commands(
                    f"/data merge block {BASES[case]} {Y} {Z} {{ScrollValue:16}}" for case in range(len(BASES))
                )
            control.step_to(start + tick)
            for row in sample(control, tick):
                actual[row[:3]] = row[3:]
        differences = [
            (key, expected.get(key), actual[key]) for key in sorted(actual) if expected.get(key) != actual[key]
        ]
    if differences:
        raise RuntimeError(
            f"{len(differences)} of {len(expected)} competing-motor samples differ from Java. "
            f"First: {differences[:8]}"
        )
    print(f"Two Creative Motors sharing one shaft matched all {len(expected)} Java samples.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
