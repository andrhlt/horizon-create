#!/usr/bin/env python3
"""Compare shaft and gear-train speed throughout a power interruption."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/wheat_milling.nbt")
ORIGIN = (3, 96, -12)
MOTOR = "create:creative_motor[facing=east]"
ASSEMBLY = (
    ((1, 9, 1), MOTOR),
    ((2, 9, 1), "create:shaft[axis=x]"),
    ((3, 9, 1), "create:large_cogwheel[axis=x]"),
    ((3, 10, 2), "create:cogwheel[axis=x]"),
    ((4, 10, 2), "create:shaft[axis=x]"),
    ((3, 11, 2), "create:cogwheel[axis=x]"),
    ((4, 9, 2), "create:large_cogwheel[axis=z]"),
    ((4, 9, 3), "create:shaft[axis=z]"),
    ((1, 9, 8), MOTOR),
    ((2, 9, 8), "create:cogwheel[axis=x]"),
    ((2, 10, 9), "create:large_cogwheel[axis=x]"),
    ((3, 10, 9), "create:shaft[axis=x]"),
)


def position(relative):
    x, y, z = (base + delta for base, delta in zip(ORIGIN, relative, strict=True))
    return f"{x} {y - 1} {z}"


def sample(control, tick):
    tags = control.commands(
        f"/data get block {position(relative)}" for relative, state in ASSEMBLY if state != MOTOR
    )
    row = [str(tick)]
    for tag in tags:
        if "create:simple_kinetic" not in tag:
            raise RuntimeError(f"Missing gear or shaft block entity: {tag}")
        speed = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)", tag)
        if not speed and tick:
            raise RuntimeError(f"No speed at tick {tick}: {tag}")
        row.append(str(int(float(speed[1]))) if speed else "0")
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    args = parser.parse_args()
    with (ROOT / "fixtures/shaft_and_cogwheel-java.csv").open() as file:
        rows = csv.reader(file)
        header, expected = next(rows), list(rows)
    actual = []
    with fixture_world(args, "Gear-trains", STRUCTURE, render=True) as control:
        control.commands(f"/setblock {position(pos)} {block}" for pos, block in ASSEMBLY)
        first_motor = position(ASSEMBLY[0][0])
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
            if tick in (10, 24):
                changed_to = "minecraft:air" if tick == 10 else MOTOR
                control.command(f"/setblock {first_motor} {changed_to}")
        control.command("/fill 2 102 -14 10 102 -3 minecraft:smooth_stone")
        control.command("/time set noon")
        control.call("tp", 10.3, 103, -7.0)
        control.call("look-at", 5.9, 104.8, -10.6)
        control.call("key", "f1", "tap")
        control.call("wait", 5)
        control.call("screenshot", ROOT / ".local/shaft_and_cogwheel.png")
    path = ROOT / ".local/shaft_and_cogwheel-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"Gear trains differ in {len(differences)} rows. "
                         f"First rows (Java, Horizon): {differences[:5]}")
    print(f"Gear trains matched all {len(actual)} Java ticks. See {path}")


if __name__ == "__main__":
    main()
