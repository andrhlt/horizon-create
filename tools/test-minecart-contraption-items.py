#!/usr/bin/env python3
"""Check the original minecart contraption and coupling recipes in survival."""
import argparse
from pathlib import Path

from fixture_world import fixture_world
from importlib import import_module

crafting = import_module("test-survival-crafting")


def run(args):
    with fixture_world(args, "MinecartContraptionItems", render=True, pack=args.pack) as world:
        world.command("/gamemode survival")
        for item, result in (("minecart_contraption", "minecraft:minecart"),
                             ("furnace_minecart_contraption", "minecraft:furnace_minecart"),
                             ("chest_minecart_contraption", None)):
            world.commands(("/clear @s", f"/item replace entity @s hotbar.0 with create:{item} 2"))
            world.call("open-inventory")
            crafting.distribute(world, 0, (100,))
            world.call("click-slot", 0)
            if result:
                crafting.craft(world, result, 1)
                counts = world.call("inventory")["counts"]
                if counts.get(f"create:{item}") != 1:
                    raise RuntimeError(f"{item}: crafting did not consume exactly one item: {counts}")
            else:
                menu = world.call("menu")
                result_slot = next((entry["stack"] for entry in menu["slots"] if entry["slot"] == 200), None)
                if result_slot:
                    raise RuntimeError(f"{item}: unexpected conversion output {result_slot}")
            world.call("close")
        world.commands((
            "/clear @s",
            "/fill 5 104 -15 13 104 -9 minecraft:smooth_stone",
            "/setblock 11 105 -12 minecraft:crafting_table",
            "/tp @s 10.4 105 -11.5",
            "/item replace entity @s hotbar.0 with create:andesite_alloy 2",
            "/item replace entity @s hotbar.1 with create:iron_sheet",
        ))
        world.call("wait", 3)
        world.call("interact", 11, 105, -12, "west")
        crafting.distribute(world, crafting.inventory_slot(world, "create:andesite_alloy"), (102, 106))
        crafting.distribute(world, crafting.inventory_slot(world, "create:iron_sheet"), (104,))
        crafting.craft(world, "create:minecart_coupling", 1)
        counts = world.call("inventory")["counts"]
        assert not counts.get("create:andesite_alloy") and not counts.get("create:iron_sheet"), counts
    print("Both cart conversion recipes and the Minecart Coupling recipe passed. Chest carts had no conversion.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
