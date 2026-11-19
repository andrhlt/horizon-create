#!/usr/bin/env python3
"""Replay Create's original arm-fed mechanical crafting grid."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/crushing_wheel_crafting.nbt")
CRAFTERS = ("6 97 -9", "7 98 -9", "8 100 -9", "5 99 -9")


def number(nbt, key):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", nbt)
    return float(match[1]) if match else 0.0


def sample(control, tick):
    results = iter(control.commands((
        *(command for pos in CRAFTERS for command in
          (f"/data get block {pos}", f"/data get block {pos} Items",
           f"/data get block {pos} GroupedItems.Grid")),
        "/data get block 4 99 -9 Items",
    )))
    values = [str(tick)]
    for _ in CRAFTERS:
        body, held, grid = next(results), next(results), next(results)
        mode = re.search(r'\bPhase: "([A-Z]+)"', body)
        if not mode:
            raise RuntimeError(f"Missing original mechanical crafter: {body}")
        values.extend((
            f'{number(body, "Speed"):.4f}', mode[1], str(int(number(body, "CountDown"))),
            str(int(number(held, "count"))), str(grid.count("item:")),
        ))
    chest = next(results)
    wheels = sum(int(number(slot, "count")) for slot in re.findall(r"\{[^{}]*\}", chest)
                 if 'id: "create:crushing_wheel"' in slot)
    return [*values, str(wheels)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()
    with (ROOT / "fixtures/crushing_wheel_crafting-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)[:args.ticks]
    actual = []
    with fixture_world(args, "Crushing-wheel-crafting", STRUCTURE) as control:
        control.command("/place template create:gametest/processing/crushing_wheel_crafting 3 96 -12")
        control.commands((
            "/setblock 5 98 -10 minecraft:lever[face=floor,facing=east,powered=false]",
            "/setblock 9 98 -10 minecraft:lever[face=floor,facing=west,powered=false]",
            "/setblock 6 102 -9 minecraft:lever[face=floor,facing=south,powered=false]",
        ))
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
    path = ROOT / ".local/crushing_wheel_crafting-horizon.csv"
    with path.open("w", newline="") as file:
        output = csv.writer(file, lineterminator="\n")
        output.writerow(header)
        output.writerows(actual)
    differences = [
        (a[0], {key: (ref, seen) for key, ref, seen in zip(header, a, b, strict=True) if ref != seen})
        for a, b in zip(expected, actual, strict=True) if a != b
    ]
    if differences:
        raise SystemExit(f"Mechanical crafting differs on {len(differences)} ticks. "
                         f"First differences (Java, Horizon): {differences[:8]}. See {path}")
    print(f"Original crushing wheel crafting matched all {len(expected)} Java ticks. See {path}")


if __name__ == "__main__":
    main()
