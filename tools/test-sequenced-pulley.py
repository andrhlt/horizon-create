#!/usr/bin/env python3
"""Compare Java's original Sequenced Gearshift, Rope Pulley, and Threshold Switch fixture."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/misc/threshold_switch_pulley.nbt")
ORIGIN_Y = 96


def number(snbt, name, default=0):
    match = re.search(rf'\b{name}: (-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)', snbt)
    return float(match[1]) if match else default


def sample(control, tick):
    gearshift, pulley, stock, magnet = control.commands((
        "/data get block 6 101 -11",
        "/data get block 5 101 -11",
        "/data get block 4 101 -11",
        "/execute if block 5 97 -11 create:pulley_magnet",
    ))
    state = control.call("block", 6, 101, -11)["state"]
    step = state.partition("state=")[2][0]
    observed = int(number(stock, "CurrentAmount") - ORIGIN_Y) if tick else 0
    return [
        str(tick), f"{number(gearshift, 'Speed'):.4f}", f"{number(pulley, 'Speed'):.4f}",
        str(int(number(gearshift, "InstructionIndex", -1))),
        str(int(number(gearshift, "InstructionDuration", -1))),
        str(int(number(gearshift, "Timer"))),
        f"{number(gearshift, 'InstructionProgress'):.5f}",
        str(int(number(pulley, "Running"))), f"{number(pulley, 'Offset'):.4f}",
        str(observed), "block.create.pulley_magnet" if magnet.startswith("Test passed") else "block.minecraft.air",
        step,
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with (ROOT / "fixtures/threshold_switch_pulley-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)

    actual = []
    with fixture_world(args, "Sequenced-pulley", STRUCTURE, pack=args.pack) as control:
        control.command("/place template create:gametest/misc/threshold_switch_pulley 3 96 -12")
        control.call("wait", 3)
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
            if tick == 10:
                control.command("/setblock 6 102 -11 minecraft:lever[face=floor,facing=west,powered=true]")

    output = ROOT / ".local/threshold_switch_pulley-horizon.csv"
    with output.open("w") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a[0], {k: (x, y) for k, x, y in zip(header, a, b, strict=True) if x != y})
                   for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"Sequenced Pulley differs on {len(differences)} ticks. "
                         f"First differences (Java, Horizon): {differences[:8]}. See {output}")
    print(f"Original Sequenced Pulley matched all {len(expected)} Java ticks. See {output}")


if __name__ == "__main__":
    main()
