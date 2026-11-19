#!/usr/bin/env python3
"""Trace Create's original heated potion mixer, filtered pipe, and spout."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/potion_brewing.nbt")


def number(snbt, key, default=0.0):
    rx = rf"\b{key}: (-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)"
    match = re.search(rx, snbt)
    return float(match[1]) if match else default


def compounds(snbt):
    text = snbt.partition("[")[2]
    start = 0
    depth = 0
    for i, char in enumerate(text):
        if char == "{":
            if depth == 0:
                start = i
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                yield text[start:i+1]


def fluid(snbt):
    id_match = re.search(r'\bpotion: "([^"]+)"', snbt) or re.search(r'\bid: "([^"]+)"', snbt)
    amount = int(number(snbt, "amount"))
    return [id_match[1] if id_match and amount > 0 else "-", str(amount)]


def sample(control, tick):
    mix, spout, input_tanks, output_tanks, spout_tank, inventory, output = control.commands((
        "/data get block 7 100 -9",
        "/data get block 11 99 -9",
        "/data get block 7 98 -9 InputTanks",
        "/data get block 7 98 -9 OutputTanks",
        "/data get block 11 99 -9 Tanks",
        "/data get block 7 98 -9 Items",
        "/data get block 11 98 -7 Items",
    ))
    values = [str(tick), f'{number(mix, "Speed"):.4f}',
              *(str(int(number(mix, key))) for key in ("Running", "Ticks", "ProcessingTicks")),
              str(int(number(spout, "ProcessingTicks", -1)))]
    for snbt, slots in ((input_tanks, 2), (output_tanks, 2), (spout_tank, 1)):
        tanks = list(compounds(snbt))
        for slot in range(slots):
            values.extend(fluid(tanks[slot]) if slot < len(tanks) else ("-", "0"))
    for identity in ("minecraft:nether_wart", "minecraft:glistering_melon_slice"):
        values.append(str(sum(int(number(stack, "count")) for stack in compounds(inventory)
                              if f'id: "{identity}"' in stack)))
    values.append(str(sum(int(number(stack, "count")) for stack in compounds(output)
                          if 'potion: "minecraft:healing"' in stack and 'id: "minecraft:potion"' in stack)))
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()
    with (ROOT / "fixtures/potion_brewing-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)[:args.ticks]
    actual = []
    with fixture_world(args, "Potion-brewing", STRUCTURE) as control:
        control.command("/place template create:gametest/processing/potion_brewing 3 96 -12")
        control.command("/setblock 5 98 -8 minecraft:lever[face=floor,facing=north,powered=false]")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
            if tick == 300:
                control.command("/setblock 10 98 -10 minecraft:lever[face=floor,facing=south,powered=false]")
    path = ROOT / ".local/potion_brewing-horizon.csv"
    with path.open("w", newline="") as file:
        output = csv.writer(file, lineterminator="\n")
        output.writerow(header)
        output.writerows(actual)
    differences = [(a[0], {k: (r,h) for k,r,h in zip(header,a,b,strict=True) if r != h})
                   for a,b in zip(expected,actual,strict=True) if a != b]
    if differences:
        raise SystemExit(f"Potion brewing differs on {len(differences)} ticks. "
                         f"First differences (Java, Horizon): {differences[:8]}. See {path}")
    print(f"Original potion brewing matched all {len(expected)} Java ticks. See {path}")


if __name__ == "__main__":
    main()
