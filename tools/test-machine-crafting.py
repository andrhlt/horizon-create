#!/usr/bin/env python3
"""Replay the pinned Java Create crafting recipes using Horizon's survival grid."""

import argparse
from collections import Counter, defaultdict
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

crafting = import_module("test-survival-crafting")


def replay(control, recipe):
    control.command("/clear @s")
    slots = defaultdict(list)
    width = int(recipe["width"])
    for index, item in enumerate(recipe["slots"].split(",")):
        if item != "_":
            row, column = divmod(index, width)
            slots[item].append(100 + row * 3 + column)
    control.commands(
        f"/item replace entity @s hotbar.{index} with {item} {len(cells)}"
        for index, (item, cells) in enumerate(slots.items())
    )
    control.call("wait", 3)
    control.call("interact", 12, 170, 24, "up")
    for index, cells in enumerate(slots.values()):
        crafting.distribute(control, index, cells)

    output = recipe["output"]
    count = int(recipe["count"])
    crafting.craft(control, output, count)
    control.call("close")
    control.call("wait", 3)
    expected = Counter({output: count})
    for remainder in filter(None, recipe["remainder"].split(",")):
        item, quantity = remainder.rsplit(":", 1)
        expected[item] += int(quantity)
    actual = control.call("inventory")["counts"]
    if actual != expected:
        raise RuntimeError(f'{recipe["recipe"]} left {actual}, expected {dict(expected)}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/machine-crafting-java.csv")
    parser.add_argument("--check-missing", action="store_true")
    args = parser.parse_args()

    with args.reference.open(newline="") as source:
        recipes = list(csv.DictReader(source))
    with fixture_world(args, "Machine-crafting", render=True, pack=args.pack) as control:
        if args.check_missing:
            replies = control.commands(f'/recipe give @s create:{row["recipe"]}' for row in recipes)
            for row, reply in zip(recipes, replies, strict=True):
                if "unknown recipe" not in reply.lower():
                    raise RuntimeError(f'{row["recipe"]} was already loaded: {reply}')
            print(f"Baseline is missing all {len(recipes)} original recipe IDs.")
            return
        control.commands((
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))
        for row in recipes:
            replay(control, row)
            print(f'{row["recipe"]} matched Java Create.', flush=True)
    print(f"All {len(recipes)} Java recipes matched output and remaining items in survival.")


if __name__ == "__main__":
    main()
