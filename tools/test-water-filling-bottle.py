#!/usr/bin/env python3
"""Replay the original water bottle factory and item launch."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/water_filling_bottle.nbt")


def number(text, key, default=0.0):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)", text)
    return float(match[1]) if match else default


def sample(control, tick):
    belt, loaded, pump, nozzle, ejector, flying, chute, item, barrel = control.commands((
        "/data get block 5 97 -9",
        "/data get block 5 97 -9 Inventory.Items",
        "/data get block 7 98 -9",
        "/data get block 5 99 -11",
        "/data get block 5 97 -11",
        "/data get block 5 97 -11 LaunchedItems",
        "/data get block 5 98 -8",
        "/data get block 5 98 -8 Items",
        "/data get block 5 97 -8 Items",
    ))
    state = re.search(r'\bState: "([A-Z]+)"', ejector)
    if not state:
        raise RuntimeError(f"Cannot read the original Weighted Ejector: {ejector}")
    stacks = []
    for cargo in re.findall(r'\{([^{}]*\{[^{}]*\}[^{}]*)\}', loaded):
        identifier = re.search(r'\bid: "([^"]+)"', cargo)
        if identifier:
            count = int(number(cargo, "count", number(cargo, "Count")))
            stacks.append(f'{identifier[1]}/{count}/{number(cargo, "Pos"):.7f}')
    barrel_count = int(number(barrel, "count")) if 'potion: "minecraft:water"' in barrel else 0
    return [
        str(tick), f'{number(belt, "Speed"):.4f}', f'{number(pump, "Speed"):.4f}',
        str(int(number(nozzle, "amount"))), str(int(number(nozzle, "ProcessingTicks", -1))),
        f'{number(ejector, "Speed"):.4f}', state[1], f'{number(ejector, "Value", 1):.7f}',
        str(flying.count("Time:")), str(int(number(item, "count"))),
        f'{number(chute, "ItemPosition", 0.5):.7f}', str(barrel_count), ";".join(stacks) or "-",
    ]


def matching(ref, seen):
    if any(ref[i] != seen[i] for i in (0, 1, 2, 3, 4, 5, 6, 8, 9, 11)):
        return False
    if any(abs(float(ref[i]) - float(seen[i])) > 1e-6 for i in (7, 10)):
        return False
    if ref[12] == seen[12]:
        return True
    left, right = (v.split("/") for v in (ref[12], seen[12]))
    return len(left) == len(right) == 3 and left[:2] == right[:2] and abs(float(left[2]) - float(right[2])) <= 1e-6


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    args = parser.parse_args()
    with (ROOT / "fixtures/water_filling_bottle-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    actual = []
    with fixture_world(args, "Water-filling-bottle", STRUCTURE) as control:
        control.command("/place template create:gametest/processing/water_filling_bottle 3 96 -12")
        control.command("/setblock 6 98 -9 minecraft:lever[face=floor,facing=north,powered=false]")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
    path = ROOT / ".local/water_filling_bottle-horizon.csv"
    with path.open("w", newline="") as file:
        output = csv.writer(file, lineterminator="\n")
        output.writerow(header)
        output.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True) if not matching(a, b)]
    if differences:
        raise SystemExit(f"Water bottle filling differs on {len(differences)} ticks. "
                         f"First differences (Java, Horizon): {differences[:4]}. See {path}")
    print(f"Original water bottle factory matched all {len(actual)} Java ticks. See {path}")


if __name__ == "__main__":
    main()
