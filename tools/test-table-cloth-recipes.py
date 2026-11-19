#!/usr/bin/env python3
"""Exercise Table Cloth crafting, dyeing, and all three stonecutting recipes."""
import argparse
from pathlib import Path
from fixture_world import fixture_world
import importlib.util

def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

crafting = load("test-survival-crafting")
craft, distribute, inventory_slot = crafting.craft, crafting.distribute, crafting.inventory_slot
stone = load("test-stone-palettes")
selection, wait_for = stone.selection, stone.wait_for


def run(args):
    with fixture_world(args, "Cloth-recipes", render=True, pack=args.pack) as world:
        world.commands((
            "/fill 3 96 -11 12 96 -6 minecraft:smooth_stone",
            "/setblock 5 97 -9 minecraft:stonecutter",
            "/tp @s 3.0 97.0 -8.5 -90 20",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with minecraft:white_wool",
            "/item replace entity @s hotbar.1 with create:andesite_alloy",
            "/item replace entity @s hotbar.2 with minecraft:red_dye",
        ))
        world.call("open-inventory")
        distribute(world, 0, (100,))
        distribute(world, 1, (101,))
        craft(world, "create:white_table_cloth", 2)
        distribute(world, inventory_slot(world, "create:white_table_cloth"), (100,))
        distribute(world, 2, (101,))
        craft(world, "create:red_table_cloth", 1)
        world.call("close")
        for slot, (material, ingredient) in enumerate((
            ("andesite", "create:andesite_alloy"),
            ("brass", "create:brass_ingot"),
            ("copper", "minecraft:copper_ingot"),
        )):
            world.command(f"/item replace entity @s hotbar.{slot} with {ingredient}")
        world.call("interact", 5, 97, -9, "up")
        wait_for("Stonecutter", lambda: world.call("menu").get("station"), lambda x: x == "Stonecutter")
        for slot, (material, ingredient, suffix) in enumerate((
            ("andesite", "create:andesite_alloy", "andesite_alloy"),
            ("brass", "create:brass_ingot", "ingots_brass"),
            ("copper", "minecraft:copper_ingot", "ingots_copper"),
        )):
            world.call("click-slot", slot)
            world.call("click-slot", 600)
            name = f"create:{material}_table_cloth"
            selection(world, f"create:{material}_table_cloth_from_{suffix}_stonecutting", None)
            def result():
                return next((e["stack"] for e in world.call("menu")["slots"] if e["slot"] == 650), None)
            wait_for(name, result, lambda x: x is not None and (x["item"], x["count"]) == (name, 2))
            world.call("click-slot", 650, "shift")
            wait_for(name + " in inventory", lambda: world.call("inventory")["counts"].get(name, 0), lambda x: x == 2)
    print("Survival crafting produced two white cloths and recolored one red; all three stonecutting recipes produced two covers.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda x: Path(x).resolve())
    parser.add_argument("--pack", type=lambda x: Path(x).resolve())
    run(parser.parse_args())

if __name__ == "__main__":
    main()
