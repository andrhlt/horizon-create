#!/usr/bin/env python3
"""Craft ordinary and smart Chutes with the pinned Java recipes in survival."""

import argparse
from collections import Counter
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

crafting = import_module("test-survival-crafting")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    args = parser.parse_args()

    with fixture_world(args, "Chute-survival-crafting", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 6 169 20 18 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
            "/clear @s",
            "/item replace entity @s hotbar.0 with create:iron_sheet 2",
            "/item replace entity @s hotbar.1 with minecraft:iron_ingot",
        ))
        control.call("interact", 12, 170, 24, "up")
        crafting.distribute(control, 0, (100, 106))
        crafting.distribute(control, 1, (103,))
        crafting.craft(control, "create:chute", 4)

        control.command("/item replace entity @s hotbar.2 with create:brass_sheet")
        control.command("/item replace entity @s hotbar.3 with create:electron_tube")
        chute_slot = crafting.inventory_slot(control, "create:chute")
        brass_slot = crafting.inventory_slot(control, "create:brass_sheet")
        tube_slot = crafting.inventory_slot(control, "create:electron_tube")
        crafting.distribute(control, brass_slot, (100,))
        crafting.distribute(control, chute_slot, (103,))
        crafting.distribute(control, tube_slot, (106,))
        crafting.craft(control, "create:smart_chute", 1)
        control.call("close")

        actual = Counter(control.call("inventory")["counts"])
        expected = Counter({"create:chute": 3, "create:smart_chute": 1})
        if actual != expected:
            raise RuntimeError(f"Survival chute crafting left {dict(actual)}, expected {dict(expected)}")

    print("Survival crafting matched the pinned Chute (4x) and Smart Chute (1x) recipes.")


if __name__ == "__main__":
    main()
