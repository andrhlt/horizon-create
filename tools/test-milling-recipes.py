#!/usr/bin/env python3
"""Compare three more milling recipes in the original wheat milling structure."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/wheat_milling.nbt")
BARREL = "5 102 -11"
MILL = "5 98 -11"
HOPPER = "5 97 -11"
CHEST = "4 97 -11"
RECIPES = {
    "clay": ("clay", "clay_ball", None),
    "wool": ("magenta_wool", "string", None),
    "bone": ("bone", "bone_meal", "white_dye"),
}


def counts(tag, items, slots=None):
    totals = [0] * len(items)
    for stack in re.findall(r"\{([^{}]*\bid: \"minecraft:[^{}]+)\}", tag):
        item = re.search(r'\bid: "minecraft:([^"]+)"', stack)[1]
        if item not in items:
            continue
        slot = re.search(r"\bSlot: (\d+)", stack)
        if slots and (not slot or not slots(int(slot[1]))):
            continue
        count = re.search(r"\b(?:count|Count): (\d+)", stack)
        totals[items.index(item)] += int(count[1]) if count else 1
    return totals


def sample(control, tick, recipe):
    input_item, output, bonus = recipe
    supply, machine, hopper, chest = control.commands(
        f"/data get block {pos}" for pos in (BARREL, MILL, HOPPER, CHEST)
    )
    if "create:millstone" not in machine:
        raise RuntimeError(f"Fixture mill missing: {machine}")
    timer = re.search(r"\bTimer: (-?\d+)", machine)[1]
    return list(map(str, (
        tick,
        *counts(supply, (input_item,)),
        *counts(machine, (input_item,), lambda slot: slot == 0),
        timer,
        *counts(machine, (output, bonus), lambda slot: slot > 0),
        *counts(hopper, (output, bonus)),
        *counts(chest, (output, bonus)),
    )))


def run(args, name):
    recipe = RECIPES[name]
    with (ROOT / f"fixtures/milling_{name}-java.csv").open() as file:
        rows = csv.reader(file)
        header, expected = next(rows), list(rows)
    actual = []
    env = {"CREATE_WHEAT_TRACE_ORIGIN": "3,96,-12", "CREATE_WHEAT_TRACE_SEED": "2"}
    with fixture_world(args, f"Milling-{name}", STRUCTURE, env=env) as control:
        control.command("/place template create:gametest/processing/wheat_milling 3 96 -12")
        control.commands((
            f"/item replace block {BARREL} container.13 with minecraft:air",
            f"/item replace block {BARREL} container.0 with minecraft:{recipe[0]}",
            "/setblock 4 102 -11 minecraft:lever[face=wall,facing=west,powered=false]",
        ))
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick, recipe))

    output = ROOT / f".local/milling_{name}-horizon.csv"
    with output.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"{name} differs in {len(differences)} rows. "
                         f"First rows (Java, Horizon): {differences[:5]}")
    print(f"Milling {name} matched all {len(actual)} Java ticks. See {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--recipe", choices=RECIPES, action="append")
    args = parser.parse_args()
    for recipe in args.recipe or RECIPES:
        run(args, recipe)


if __name__ == "__main__":
    main()
