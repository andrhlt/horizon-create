#!/usr/bin/env python3
"""Check the original Crafter Slot Cover recipe and survival use."""

import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

crafting = import_module("test-survival-crafting")
COVER = "create:crafter_slot_cover"


def block_data(world):
    return world.command("/data get block 8 105 -12")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()

    with fixture_world(args, "CrafterSlotCover", render=True, pack=args.pack) as world:
        world.commands((
            "/fill 5 104 -15 13 104 -9 minecraft:smooth_stone",
            "/fill 5 105 -15 13 107 -9 minecraft:air",
            "/setblock 8 105 -12 create:mechanical_crafter[facing=east]",
            "/tp @s 10.4 105 -11.5",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:brass_nugget 3",
        ))
        world.call("wait", 3)
        world.command("/setblock 11 105 -12 minecraft:crafting_table")
        world.call("interact", 11, 105, -12, "west")
        crafting.distribute(world, crafting.inventory_slot(world, "create:brass_nugget"), (100, 101, 102))
        crafting.craft(world, COVER, 1)
        slot = crafting.inventory_slot(world, COVER)
        if slot >= 9:
            world.call("click-slot", slot)
            world.call("click-slot", 0)
        world.call("close")
        world.call("select", COVER)
        world.call("wait", 3)
        placed = world.call("block", 8, 105, -12)["state"]
        assert "facing=east" in placed, placed
        world.call("look-at", 8.98, 105.5, -11.5)
        world.call("mouse", "right", "click")
        world.call("wait", 3)
        assert "Cover: 1b" in block_data(world), (block_data(world), world.call("inventory")["hotbar"])
        world.call("mouse", "right", "click")
        world.call("wait", 3)
        assert "Cover: 0b" in block_data(world), block_data(world)
        crafting.inventory_slot(world, COVER)

    print("The original recipe crafted a cover, and survival installation and removal passed.")


if __name__ == "__main__":
    main()
