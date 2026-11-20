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
        ))
        # Java's setValue(16) skips the callback for a freshly placed motor.
        if case == 1:
            commands.append(f"/data merge block {base + 2} {Y} {Z} {{ScrollValue:-16}}")
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
    with (ROOT / "fixtures/creative-motor-competition-isolated-java.csv").open() as stream:
        expected = {
            (int(row["tick"]), int(row["case"]), int(row["offset"])): (int(row["present"]), float(row["speed"]))
            for row in csv.DictReader(stream)
        }
    with fixture_world(args, "CreativeMotorCompetition", pack=args.pack) as control:
        setup(control)
        start = control.clock()
        actual = {}
        for tick in range(TICKS):
            if tick > 0:
                control.step_to(start + tick)
            for row in sample(control, tick):
                actual[row[:3]] = row[3:]
            # The Java GameTest samples each lane before acting on that lane.
            if tick == 5:
                for case, base in enumerate(BASES):
                    if actual[tick, case, 2][0]:
                        setting = -16 if case == 0 else 16
                        control.command(f"/data merge block {base + 2} {Y} {Z} {{ScrollValue:{setting}}}")
            if tick == 12:
                control.commands(f"/setblock {BASES[case]} {Y} {Z} minecraft:air" for case in range(len(BASES)))
            if tick == 18:
                control.commands(
                    f"/setblock {BASES[case]} {Y} {Z} create:creative_motor[facing=east]" for case in range(len(BASES))
                )
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("tick", "case", "offset", "present", "speed"))
        writer.writerows((*key, *actual[key]) for key in sorted(actual))
    if actual.keys() != expected.keys():
        raise RuntimeError(f"Competition trace keys differ: {actual.keys() ^ expected.keys()}.")
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
    parser.add_argument("--output", type=Path, default=ROOT / ".local/creative-motor-competition-horizon.csv")
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
