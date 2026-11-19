#!/usr/bin/env python3
"""Replay the original sand_washing GameTest against its seeded Java trace."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/sand_washing.nbt")
COUNT = re.compile(r'\b(?:Count|count): (\d+)')
STACK = re.compile(r'\{(?=[^{}]*\bItem: \{)(.*?)\}(?=, \{|\])', re.S)


def item(fragment):
    count = COUNT.search(fragment)
    identity = re.search(r'\bid: "([\w:]+)"', fragment)
    pos = re.search(r'\bPos: (-?\d+(?:\.\d+)?)', fragment)
    timer = re.search(r'\bFanProcessingTime: (-?\d+)', fragment)
    if not count or not pos or not identity:
        raise RuntimeError(f"Could not decode belt stack: {fragment}")
    return (identity[1], count[1], f"{float(pos[1]):.7f}", timer[1] if timer else "-2")


def sample(control, tick):
    funnel, chest, belt = control.commands((
        "/data get block 8 98 -10 TransferCooldown",
        "/data get block 11 98 -10 Items",
        "/data get block 10 97 -10 Inventory",
    ))
    cooldown = re.search(r'has the following block data: (\d+)', funnel)
    stacks = []
    for line in re.findall(r'\{(?:[^{}]|\{[^{}]*\})*\}', belt):
        if "Item:" in line:
            stacks.append(item(line))
    if "Items: [" in belt and not stacks and "Item:" in belt:
        # The outer Inventory brace contains a list of compounds with item NBT.
        stacks = [item(match) for match in STACK.findall(belt)]
    if len(stacks) != belt.count("Item: {"):
        raise RuntimeError(f"Could not read transported stacks: {belt}")
    return [str(tick), cooldown[1] if cooldown else "0",
            str(sum(map(int, COUNT.findall(chest)))),
            ";".join(":".join(stack) for stack in stacks)]


def equal(expected, actual):
    if expected[:3] != actual[:3]:
        return False
    java = [entry.rsplit(":", 3) for entry in expected[3].split(";") if entry]
    horizon = [entry.rsplit(":", 3) for entry in actual[3].split(";") if entry]
    return len(java) == len(horizon) and all(
        a[:2] == b[:2] and a[3] == b[3] and abs(float(a[2]) - float(b[2])) <= 0.000001
        for a, b in zip(java, horizon, strict=True)
    )


def run(args):
    with (ROOT / "fixtures/sand_washing-java.csv").open() as file:
        rows = csv.reader(file)
        header, expected = next(rows), list(rows)
    actual = []
    with fixture_world(args, "Sand-washing", STRUCTURE, env={"CREATE_FAN_TRACE_SEED": "4096"}) as control:
        control.command("/place template create:gametest/processing/sand_washing 3 96 -12")
        control.command("/setblock 8 98 -11 minecraft:lever[face=floor,facing=south,powered=false]")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))

    path = ROOT / ".local/sand_washing-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True) if not equal(a, b)]
    if differences:
        raise SystemExit(f"Sand washing differs on {len(differences)} ticks. "
                         f"First rows (Java, Horizon): {differences[:8]}. See {path}")
    print(f"Original sand washing matched Java across {len(actual)} ticks. See {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())


if __name__ == "__main__":
    main()
