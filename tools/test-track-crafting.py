#!/usr/bin/env python3
"""Replay Create's original three-stage railway track assembly."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/track_crafting.nbt")


def field(nbt, key, default=0.0):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", nbt)
    return float(match[1]) if match else default


def stack_count(nbt):
    return int(field(nbt, "count", field(nbt, "Count")))


def compounds(nbt):
    depth = 0
    start = 0
    sequence = nbt.partition("[")[2]
    for index, char in enumerate(sequence):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                yield sequence[start:index + 1]


def cargo(nbt):
    result = []
    for compound in compounds(nbt):
        if not stack_count(compound):
            continue
        item = re.search(r'\bid: "((?:minecraft|create):[a-z_]+)"', compound)
        if not item:
            raise RuntimeError(f"Missing item ID in {compound}")
        item_id = item[1]
        result.append(
            f'{item_id}/{stack_count(compound)}/{int(field(compound, "step"))}/'
            f'{field(compound, "Pos"):.7f}/{int(field(compound, "Locked"))}'
        )
    return ";".join(result) or "-"


def sample(control, tick):
    iron, iron_items, zinc, zinc_items, press, chest, belt = control.commands((
        "/data get block 6 99 -10",
        "/data get block 6 99 -10 Items",
        "/data get block 7 99 -10",
        "/data get block 7 99 -10 Items",
        "/data get block 8 99 -10",
        "/data get block 10 98 -10 Items",
        "/data get block 9 97 -10 Inventory.Items",
    ))
    result = [str(tick)]
    for deployer, items in ((iron, iron_items), (zinc, zinc_items)):
        state = re.search(r'\bState: "([A-Z]+)"', deployer)
        if "create:deployer" not in deployer or not state:
            raise RuntimeError(f"Missing original deployer in {deployer}")
        result.extend((f'{field(deployer, "Speed"):.4f}', state[1],
                       str(int(field(deployer, "Timer"))), str(stack_count(items))))
    tracks = sum(stack_count(stack) for stack in compounds(chest) if 'id: "create:track"' in stack)
    result.extend((f'{field(press, "Speed"):.4f}', str(int(field(press, "Running"))),
                   str(int(field(press, "Ticks"))), str(tracks), cargo(belt)))
    return result


def same_cargo(reference, actual):
    expected = [item.split("/") for item in reference.split(";")]
    observed = [item.split("/") for item in actual.split(";")]
    if len(expected) != len(observed):
        return False
    if expected == observed:
        return True
    return all(
        len(a) == len(b) == 5 and a[:3] == b[:3] and a[4] == b[4]
        and abs(float(a[3]) - float(b[3])) <= 0.000001
        for a, b in zip(expected, observed)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()
    with (ROOT / "fixtures/track_crafting-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)[:args.ticks]
    actual = []
    with fixture_world(args, "Track-crafting", STRUCTURE) as control:
        control.command("/place template create:gametest/processing/track_crafting 3 96 -12")
        registered = control.command("/execute if block 9 97 -10 create:belt run say Track fixture ready")
        if "Track fixture ready" not in registered:
            raise RuntimeError(f"Cannot verify the original belt: {registered}")
        control.command("/setblock 5 98 -11 minecraft:lever[face=floor,facing=south,powered=false]")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
    path = ROOT / ".local/track_crafting-horizon.csv"
    with path.open("w", newline="") as file:
        output = csv.writer(file, lineterminator="\n")
        output.writerow(header)
        output.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True)
                   if a[:-1] != b[:-1] or not same_cargo(a[-1], b[-1])]
    if differences:
        raise SystemExit(f"Track crafting differs on {len(differences)} ticks. First (Java, Horizon): "
                         f"{differences[:4]}. See {path}")
    print(f"Track crafting matched all {len(actual)} Java ticks. See {path}")


if __name__ == "__main__":
    main()
