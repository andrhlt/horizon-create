#!/usr/bin/env python3
"""Replay the original four-belt fifteen-operation Precision Mechanism assembly."""

import argparse
from collections import Counter
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/precision_mechanism_crafting.nbt")
BELTS = ("13 97 -7", "13 97 -9", "4 97 -9", "4 97 -11")
DEPLOYERS = ("10 99 -7", "6 99 -9", "12 99 -11")


def field(text, key):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)", text)
    return float(match[1]) if match else 0.0


def compounds(text):
    depth = 0
    starts = 0
    chunks = text.partition("[")[2]
    for i, char in enumerate(chunks):
        if char == "{":
            if depth == 0:
                starts = i
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                yield chunks[starts:i + 1]


def stacks(text):
    for entry in compounds(text):
        count = int(field(entry, "count") or field(entry, "Count"))
        item = re.search(r'\bid: "((?:create|minecraft):[a-z_]+)"', entry)
        if count and item:
            yield entry, count, item[1]


def belt_summary(text):
    cargo = [f'{item}/{count}/{int(field(entry, "step"))}/{field(entry, "Pos"):.7f}/{int(field(entry, "Locked"))}'
             for entry, count, item in stacks(text)]
    return ";".join(cargo) or "-"


def sample(control, tick):
    replies = iter(control.commands((
        *(cmd for pos in BELTS for cmd in (f"/data get block {pos}", f"/data get block {pos} Inventory.Items")),
        *(cmd for pos in DEPLOYERS for cmd in (f"/data get block {pos}", f"/data get block {pos} Items")),
        "/data get block 14 98 -11 Items",
    )))
    values = [str(tick)]
    for _ in BELTS:
        belt, items = next(replies), next(replies)
        values.extend((f'{field(belt, "Speed"):.4f}', belt_summary(items)))
    for _ in DEPLOYERS:
        deployer, held = next(replies), next(replies)
        state = re.search(r'\bState: "([A-Z]+)"', deployer)
        if not state:
            raise RuntimeError(f"Cannot read original deployer: {deployer}")
        values.extend((f'{field(deployer, "Speed"):.4f}', state[1],
                       str(int(field(deployer, "Timer"))), str(int(field(held, "count")))))
    output = Counter()
    for _, count, item in stacks(next(replies)):
        output[item] += count
    values.append("{" + ",".join(f"{item}={n}" for item, n in sorted(output.items())) + "}" if output else "-")
    return values


def same_cargo(reference, actual):
    if reference == actual:
        return True
    left, right = ([value.split("/") for value in cargo.split(";")] for cargo in (reference, actual))
    return len(left) == len(right) and all(len(a) == len(b) == 5 and a[:3] == b[:3] and a[4] == b[4]
        and abs(float(a[3]) - float(b[3])) <= 0.000001 for a, b in zip(left, right, strict=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()
    with (ROOT / "fixtures/precision_mechanism_crafting-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)[:args.ticks]
    actual = []
    with fixture_world(args, "Precision-mechanism", STRUCTURE, env={"CREATE_ASSEMBLY_TRACE_SEED": "0"}) as control:
        control.command("/place template create:gametest/processing/precision_mechanism_crafting 3 96 -12")
        control.command("/setblock 9 98 -6 minecraft:lever[face=floor,facing=west,powered=false]")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
    path = ROOT / ".local/precision_mechanism_crafting-horizon.csv"
    with path.open("w", newline="") as file:
        output = csv.writer(file, lineterminator="\n")
        output.writerow(header)
        output.writerows(actual)
    differences = []
    for ref, seen in zip(expected, actual, strict=True):
        delta = {field: (a, b) for index, (field, a, b) in enumerate(zip(header, ref, seen, strict=True))
                 if (not same_cargo(a, b) if index in (2, 4, 6, 8) else a != b)}
        if delta:
            differences.append((ref[0], delta))
    if differences:
        raise SystemExit(f"Precision mechanisms differ on {len(differences)} ticks. "
                         f"First differences (Java, Horizon): {differences[:5]}. See {path}")
    print(f"Original Precision Mechanism factory matched all {len(actual)} Java ticks. See {path}")


if __name__ == "__main__":
    main()
