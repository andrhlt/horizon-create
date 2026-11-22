#!/usr/bin/env python3
"""Craft and equip Engineer's Goggles and capture their Analog Lever overlay."""

import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

crafting = import_module("test-survival-crafting")


def run(args):
    with fixture_world(args, "Goggles", render=True) as control:
        control.commands((
            "/fill 4 96 -13 10 96 -5 minecraft:smooth_stone",
            "/setblock 6 97 -5 minecraft:crafting_table",
            "/item replace entity @s hotbar.0 with minecraft:string",
            "/item replace entity @s hotbar.1 with minecraft:glass 2",
            "/item replace entity @s hotbar.2 with create:golden_sheet",
            "/gamemode survival",
            "/tp @s 6.5 97 -6.5 0 40",
        ))
        control.call("wait", 5)
        control.call("use-item")
        control.call("wait", 5)
        crafting.distribute(control, 0, (101,))
        crafting.distribute(control, 1, (103, 105))
        crafting.distribute(control, 2, (104,))
        crafting.craft(control, "create:goggles", 1)
        slot = crafting.inventory_slot(control, "create:goggles")
        if slot != 0:
            control.call("click-slot", slot)
            control.call("click-slot", 0)
        control.call("close")

        control.command("/tp @s 6.5 97 -6.5 180 0")
        control.call("key", "1", "tap")
        control.call("wait", 5)
        control.call("use-item")
        control.call("wait", 5)
        equipment = control.command("/data get entity @s equipment.head")
        if 'id: "create:goggles"' not in equipment:
            raise RuntimeError(f"Right-click did not equip the Goggles: {equipment}")

        control.call("key", "f5", "tap")
        control.call("key", "f5", "tap")
        control.call("wait", 5)
        control.call("screenshot", ROOT / ".local/goggles-worn.png")
        control.call("key", "f5", "tap")
        control.commands((
            "/setblock 6 97 -9 create:analog_lever[face=floor,facing=north]{State:7,ChangeTimer:0}",
            "/tp @s 6.5 97 -7.5 180 52",
        ))
        control.call("wait", 30)
        control.call("screenshot", ROOT / ".local/goggles-analog.png")
        control.commands((
            "/item replace entity @s armor.head with minecraft:air",
            "/item replace entity @s hotbar.0 with create:goggles",
        ))
        equipment = control.command("/data get entity @s equipment.head")
        held = control.call("inventory")["held"]
        if 'id: "create:goggles"' in equipment or (held or {}).get("item") != "create:goggles":
            raise RuntimeError(f"Held-only control did not leave the Goggles unworn: {equipment}; {held}")
        control.call("wait", 30)
        control.call("screenshot", ROOT / ".local/goggles-analog-no-helmet.png")
    print("Crafted Engineer's Goggles in survival, equipped them with right-click and captured the HUD.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
