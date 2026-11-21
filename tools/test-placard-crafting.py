#!/usr/bin/env python3
"""Craft a Placard from its original item-frame and brass-sheet recipe."""

import argparse
from pathlib import Path

from fixture_world import fixture_world
from importlib import import_module

crafting = import_module("test-survival-crafting")


def run(args):
    with fixture_world(args, "Placard-crafting", render=True, pack=args.pack) as control:
        control.commands((
            "/gamemode survival",
            "/clear @s",
            "/item replace entity @s hotbar.0 with minecraft:item_frame",
            "/item replace entity @s hotbar.1 with create:brass_sheet",
        ))
        control.call("open-inventory")
        crafting.distribute(control, crafting.inventory_slot(control, "minecraft:item_frame"), (100,))
        crafting.distribute(control, crafting.inventory_slot(control, "create:brass_sheet"), (101,))
        crafting.craft(control, "create:placard", 1)
        counts = control.call("inventory")["counts"]
        if counts != {"create:placard": 1}:
            raise RuntimeError(f"Placard recipe left unexpected inventory: {counts}")
    print("The survival Placard recipe consumed an Item Frame and Brass Sheet and crafted one Placard.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
