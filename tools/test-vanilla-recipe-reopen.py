#!/usr/bin/env python3
"""Keep an unfinished vanilla crafting input through a world reopen."""

import argparse
from pathlib import Path

from fixture_world import fixture_world
from importlib import import_module

crafting = import_module("test-survival-crafting")


def slot_stack(world, slot):
    return next((entry["stack"] for entry in world.call("menu")["slots"]
                 if entry["slot"] == slot), None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()

    with fixture_world(args, "Vanilla-recipe-reopen", render=True, pack=args.pack) as world:
        world.command("/gamemode survival")
        world.commands((
            "/item replace entity @s hotbar.0 with minecraft:white_wool",
            "/item replace entity @s hotbar.1 with minecraft:white_wool",
        ))
        world.restart()

        after_reopen = world.call("inventory")["counts"]
        if after_reopen.get("minecraft:white_wool", 0) != 2:
            raise RuntimeError(f"The uncrafted player input did not persist: {after_reopen}")
        world.call("open-inventory")
        crafting.distribute(world, 0, (100,))
        if slot_stack(world, 200) is not None:
            raise RuntimeError(f"One persisted wool unexpectedly matched a recipe: {slot_stack(world, 200)}")
        crafting.distribute(world, 1, (101,))
        crafting.craft(world, "minecraft:white_carpet", 3)
        counts = world.call("inventory")["counts"]
        if counts.get("minecraft:white_carpet", 0) != 3 or counts.get("minecraft:white_wool", 0) != 0:
            raise RuntimeError(f"The vanilla recipe left unexpected inventory after crafting: {counts}")

    print("The single-wool negative case, persisted player input and three-carpet vanilla craft passed.")


if __name__ == "__main__":
    main()
