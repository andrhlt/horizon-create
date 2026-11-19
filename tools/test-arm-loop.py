#!/usr/bin/env python3
"""Trace two arms passing one diamond between two depots."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/items/arm_purgatory.nbt")


def field(text, key, default=0.0):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", text)
    return float(match[1]) if match else default


def count(text):
    return str(int(field(text, "count", field(text, "Count"))))


def sample(control, tick):
    depot_a, depot_b, arm_a, held_a, arm_b, held_b = control.commands((
        f"/data get block 4 97 -11 {'HeldItem' if tick == 0 else 'Items'}",
        f"/data get block 6 97 -11 {'HeldItem' if tick == 0 else 'Items'}",
        "/data get block 4 97 -9",
        "/data get block 4 97 -9 HeldItem",
        "/data get block 6 97 -9",
        "/data get block 6 97 -9 HeldItem",
    ))
    result = [str(tick), count(depot_a), count(depot_b)]
    for arm, held in ((arm_a, held_a), (arm_b, held_b)):
        phase = re.search(r'\bPhase: "([A-Z_]+)"', arm)
        if not phase or "create:mechanical_arm" not in arm:
            raise RuntimeError(f"Cannot read the original arm: {arm}")
        result += [f'{field(arm, "Speed"):.4f}', phase[1],
                   str(int(field(arm, "TargetPointIndex"))),
                   f'{field(arm, "MovementProgress"):.7f}', count(held)]
    if sum(int(result[index]) for index in (1, 2, 7, 12)) != 1:
        raise RuntimeError(f"Tick {tick} lost or duplicated the diamond: {result}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    args = parser.parse_args()
    with (ROOT / "fixtures/arm_purgatory-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    actual = []
    with fixture_world(args, "Arm-loop", STRUCTURE) as control:
        control.command("/place template create:gametest/items/arm_purgatory 3 96 -12")
        control.command("/setblock 5 98 -10 minecraft:lever[face=wall,facing=north,powered=false]")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
    path = ROOT / ".local/arm_purgatory-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a,b) for a,b in zip(expected,actual,strict=True) if a != b]
    if differences:
        raise SystemExit(f"Arm loop differs on {len(differences)} ticks. First (Java, Horizon): "
                         f"{differences[:5]}. See {path}")
    print(f"Two-arm item loop matched all {len(expected)} Java ticks. See {path}")


if __name__ == "__main__":
    main()
