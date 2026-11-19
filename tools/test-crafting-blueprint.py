#!/usr/bin/env python3
"""Check survival crafting of the original Crafting Blueprint."""

import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

crafting = import_module("test-survival-crafting")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    ingredients = ("minecraft:painting", "minecraft:crafting_table")
    with fixture_world(args, "CraftingBlueprint", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.command("/gamemode survival")
        world.commands(tuple(
            f"/item replace entity @s hotbar.{i} with {item}"
            for i, item in enumerate(ingredients)
        ))
        world.call("open-inventory")
        for i, item in enumerate(ingredients):
            crafting.distribute(world, crafting.inventory_slot(world, item), (100 + i,))
        crafting.craft(world, "create:crafting_blueprint", 1)
        counts = world.call("inventory")["counts"]
        assert all(counts.get(item, 0) == 0 for item in ingredients), counts
    print("The original recipe crafted one Crafting Blueprint and consumed both ingredients.")


if __name__ == "__main__":
    main()
