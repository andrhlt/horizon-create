#!/usr/bin/env python3
"""Craft Create's ordinary Nixie Tube in survival and place it in-world."""

import argparse
import importlib.util
from pathlib import Path

from fixture_world import fixture_world

SPEC = importlib.util.spec_from_file_location(
    "electronics_crafting", Path(__file__).with_name("test-electronics-crafting.py"))
electronics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(electronics)

ITEM = "create:nixie_tube"
TABLE = electronics.TABLE
POSITION = (11, 95, -8)
SUPPORT = (11, 94, -8)
RECIPE = next(row for row in electronics.RECIPES if row[0] == "nixie_tube")


def run(args):
    name, count, ingredients = RECIPE
    with fixture_world(args, "NixieSurvival", electronics.STRUCTURE, render=True,
                       pack=args.pack) as world:
        world.commands((
            "/fill 5 94 -12 12 94 -4 minecraft:smooth_stone",
            f"/setblock {' '.join(map(str, TABLE))} minecraft:crafting_table",
            "/tp @s 6.2 95 -7.5 -90 20",
            "/gamemode survival",
        ))
        world.call("wait", 3)
        world.command("/clear @s")
        world.commands(
            f"/item replace entity @s hotbar.{index} with {item} {len(slots)}"
            for index, (item, slots) in enumerate(ingredients)
        )
        world.call("wait", 2)
        world.call("interact", *TABLE, "west")
        world.call("wait", 3)
        for index, (_, slots) in enumerate(ingredients):
            electronics.crafting.distribute(world, index, slots)
        electronics.crafting.craft(world, ITEM, count)
        world.call("close")

        before = world.call("inventory")["counts"].get(ITEM, 0)
        assert before == count, before
        world.call("select", ITEM)
        world.command("/tp @s 11.5 95 -6.5")
        world.call("look-at", 11.5, 94.5, -7.5)
        hit = world.call("looking-at").get("block")
        assert hit and hit["pos"] == list(SUPPORT), hit
        world.call("mouse", "right", "click")
        world.call("wait", 2)
        block = world.call("block", *POSITION)
        after = world.call("inventory")["counts"].get(ITEM, 0)
        assert block["block"] == ITEM and after == count - 1, (block, after)
    print("Survival crafting made four Nixie Tubes; placing one consumed exactly one and left three.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=lambda path: Path(path).resolve(strict=True),
                        default=Path(__file__).resolve().parents[1] / ".local/create.hmod")
    run(parser.parse_args())
