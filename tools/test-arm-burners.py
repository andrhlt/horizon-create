#!/usr/bin/env python3
"""Trace one mechanical arm feeding the nine burners in the original structure."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/items/arm_multi_output.nbt")


def field(text, key, default=0.0):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", text)
    return float(match[1]) if match else default


def count(text):
    return str(int(field(text, "count", field(text, "Count"))))


def sample(control, tick):
    commands = [
        "/data get block 7 97 -10",
        "/data get block 7 97 -10 HeldItem",
        f"/data get block 5 97 -10 {'HeldItem' if tick == 0 else 'Items'}",
        *(f"/data get block {x} 97 {z}" for x in range(9, 12) for z in range(-11, -8)),
    ]
    arm, held, depot, *burners = control.commands(commands)
    phase = re.search(r'\bPhase: "([A-Z_]+)"', arm)
    if not phase or "create:mechanical_arm" not in arm:
        raise RuntimeError(f"Cannot read the original arm: {arm}")
    return [
        str(tick), f'{field(arm, "Speed"):.4f}', phase[1],
        str(int(field(arm, "TargetPointIndex"))), f'{field(arm, "MovementProgress"):.7f}',
        count(held), count(depot),
        *(str(int(field(burner, "burnTimeRemaining"))) for burner in burners),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--visual", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/arm_multi_output-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    actual = []
    with fixture_world(args, "Arm-burners", STRUCTURE, render=args.visual) as control:
        if args.visual:
            control.command("/fill 2 97 -16 14 105 -5 minecraft:air")
            control.command("/fill 4 96 -7 12 96 -4 minecraft:smooth_stone")
        control.command("/place template create:gametest/items/arm_multi_output 3 96 -12")
        control.command("/setblock 5 98 -11 minecraft:lever[face=floor,facing=west,powered=false]")
        if args.visual:
            control.command("/tp @s 7.2 97 -6.0 180 1")
            control.call("look-at", 8.1, 98.5, -9.5)
            control.call("key", "f1", "tap")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
            if args.visual and tick in (4, 9, 20, 72):
                control.call("screenshot", ROOT / f".local/arm-burners-visual-{tick}.png")
    path = ROOT / ".local/arm_multi_output-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    mismatches = [(ref, read) for ref, read in zip(expected, actual, strict=True) if ref != read]
    if mismatches:
        raise SystemExit(f"Arm burners differ on {len(mismatches)} ticks. First differences "
                         f"(Java, Horizon): {mismatches[:5]}. See {path}")
    print(f"Arm burners matched all {len(expected)} Java ticks. See {path}")


if __name__ == "__main__":
    main()
