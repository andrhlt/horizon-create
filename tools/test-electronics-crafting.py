#!/usr/bin/env python3
"""Craft Create electronics and their dependent machines in Horizon survival."""
import argparse
import importlib.util
from pathlib import Path

from fixture_world import fixture_world

spec = importlib.util.spec_from_file_location("survival_crafting", Path(__file__).with_name("test-survival-crafting.py"))
crafting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crafting)
STRUCTURE = Path("gametest/processing/wheat_milling.nbt")
TABLE = (8, 95, -8)
RECIPES = (
    ("sand_paper", 1, (("minecraft:paper", (100,)), ("minecraft:sand", (101,)))),
    ("red_sand_paper", 1, (("minecraft:paper", (100,)), ("minecraft:red_sand", (101,)))),
    ("rose_quartz", 1, (("minecraft:quartz", (104,)), ("minecraft:redstone", (100, 101, 102, 103, 105, 106, 107, 108)))),
    ("electron_tube", 1, (("create:polished_rose_quartz", (100,)), ("create:iron_sheet", (103,)))),
    ("wrench", 1, (("create:golden_sheet", (100, 101, 103)), ("create:cogwheel", (104,)), ("minecraft:stick", (107,)))),
    ("mechanical_drill", 1, (("create:andesite_alloy", (101, 103, 105)), ("minecraft:iron_ingot", (104,)), ("create:andesite_casing", (107,)))),
    ("mechanical_saw", 1, (("create:iron_sheet", (101, 103, 105)), ("minecraft:iron_ingot", (104,)), ("create:andesite_casing", (107,)))),
    ("linear_chassis", 3, (("create:andesite_alloy", (101, 107)), ("minecraft:oak_log", (103, 104, 105)))),
    ("radial_chassis", 3, (("create:andesite_alloy", (103, 105)), ("minecraft:spruce_log", (101, 104, 107)))),
    ("metal_girder", 8, (("create:iron_sheet", (100, 101, 102)), ("create:andesite_alloy", (103, 104, 105)))),
    ("encased_chain_drive", 1, (("create:andesite_casing", (100,)), ("minecraft:iron_nugget", (101, 102, 103)))),
    ("adjustable_chain_gearshift", 1, (("create:encased_chain_drive", (100,)), ("create:electron_tube", (101,)))),
    ("rotation_speed_controller", 1, (("create:precision_mechanism", (100,)), ("create:brass_casing", (103,)))),
    ("nixie_tube", 4, (("create:electron_tube", (100, 101)),)),
    ("display_board", 2, (("create:andesite_alloy", (100, 102)), ("create:electron_tube", (101,)))),
    ("brass_tunnel", 2, (("create:electron_tube", (100,)), ("create:brass_ingot", (103, 104)), ("minecraft:dried_kelp", (106, 107)))),
    ("transmitter", 1, (("minecraft:lightning_rod", (101,)), ("create:copper_sheet", (103, 104, 105)), ("minecraft:redstone", (107,)))),
    ("display_link", 1, (("create:transmitter", (100,)), ("create:brass_casing", (103,)))),
)


def run(args):
    with fixture_world(args, "Electronics", STRUCTURE, render=True) as control:
        control.commands((
            "/fill 5 94 -12 12 94 -4 minecraft:smooth_stone",
            f"/setblock {' '.join(map(str, TABLE))} minecraft:crafting_table",
            "/tp @s 6.2 95 -7.5 -90 20",
            "/gamemode survival",
        ))
        control.call("wait", 3)
        for name, count, ingredients in RECIPES:
            control.call("command", "/clear @s")
            control.commands(
                f"/item replace entity @s hotbar.{index} with {item} {len(slots)}"
                for index, (item, slots) in enumerate(ingredients)
            )
            control.call("wait", 2)
            control.call("interact", *TABLE, "west")
            control.call("wait", 3)
            for i, (_, slots) in enumerate(ingredients):
                crafting.distribute(control, i, slots)
            crafting.craft(control, f"create:{name}", count)
            control.call("wait", 3)
            counts = control.call("inventory")["counts"]
            if any(counts.get(item, 0) for item, _ in ingredients):
                raise RuntimeError(f"Unexpected leftover ingredients for {name}: {counts}")
            control.call("close")
    print(f"Survival crafting verified all {len(RECIPES)} Create electronics and machine recipes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
