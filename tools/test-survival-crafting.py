#!/usr/bin/env python3
"""Craft Create's starter parts and apply andesite alloy to stripped wood."""

import argparse
from pathlib import Path
import time

from fixture_world import fixture_world

STRUCTURE = Path("gametest/processing/wheat_milling.nbt")


def inventory_slot(control, name):
    inventory = control.call("inventory")
    slots = [*inventory["hotbar"], *inventory["main"]]
    return next(entry["slot"] for entry in slots if entry.get("item") == name)


def output(control, name, count):
    deadline = time.monotonic() + 2
    while True:
        menu = control.call("menu")
        stack = next((entry["stack"] for entry in menu["slots"] if entry["slot"] == 200), None)
        actual = (stack["item"], stack["count"]) if stack else None
        if actual == (name, count):
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Expected {count} {name} in the crafting result, got {actual}")
        time.sleep(0.05)


def craft(control, name, count):
    output(control, name, count)
    before = control.call("inventory")["counts"].get(name, 0)
    control.call("click-slot", 200, "shift")
    after = control.call("inventory")["counts"].get(name, 0)
    if after != before + count:
        raise RuntimeError(f"Expected {before + count} {name} in inventory, got {after}")


def distribute(control, source, slots):
    control.call("click-slot", source)
    for slot in slots:
        control.call("click-slot", slot, "right")


def run(args):
    with fixture_world(args, "Survival-crafting", STRUCTURE, render=True, pack=args.pack) as control:
        control.command("/fill 5 94 -12 13 94 -4 minecraft:smooth_stone")
        control.command("/setblock 9 95 -9 minecraft:stripped_oak_log")
        control.command("/setblock 9 95 -10 minecraft:oak_log")
        control.call("tp", 7.5, 95, -9.5)
        control.command("/gamemode survival")
        control.commands((
            "/item replace entity @s hotbar.0 with minecraft:andesite 6",
            "/item replace entity @s hotbar.1 with minecraft:iron_nugget 6",
            "/item replace entity @s hotbar.5 with minecraft:oak_planks 2",
        ))
        control.call("open-inventory")
        distribute(control, 0, (100, 103) * 3)
        distribute(control, 1, (101, 102) * 3)
        output(control, "create:andesite_alloy", 1)
        control.call("click-slot", 200, "shift")
        if control.call("inventory")["counts"].get("create:andesite_alloy") != 3:
            raise RuntimeError("The 2×2 recipe did not craft three alloys")
        alloy_slot = inventory_slot(control, "create:andesite_alloy")
        if alloy_slot >= 9:
            control.call("click-slot", alloy_slot)
            control.call("click-slot", 0)
        control.call("close")
        control.call("select", "create:andesite_alloy")
        control.call("interact", 9, 95, -10, "west")
        raw = control.call("block", 9, 95, -10)["state"]
        if not raw.startswith("minecraft:oak_log"):
            raise RuntimeError(f"Application changed unstripped oak: {raw}")
        control.call("interact", 9, 95, -9, "west")
        casing = control.call("block", 9, 95, -9)["state"]
        remaining = control.call("inventory")["counts"].get("create:andesite_alloy")
        if casing != "create:andesite_casing" or remaining != 2:
            raise RuntimeError(f"Application left {casing} and {remaining} alloy(s)")

        control.call("open-inventory")
        distribute(control, inventory_slot(control, "create:andesite_alloy"), (100, 102))
        craft(control, "create:shaft", 8)
        shaft_slot = inventory_slot(control, "create:shaft")
        distribute(control, shaft_slot, (100,))
        control.call("click-slot", shaft_slot)
        plank_slot = inventory_slot(control, "minecraft:oak_planks")
        distribute(control, plank_slot, (101,))
        control.call("click-slot", plank_slot)
        craft(control, "create:cogwheel", 1)
        control.call("close")
        control.command("/item replace entity @s hotbar.5 with minecraft:oak_planks 2")
        control.call("open-inventory")
        shaft_slot = inventory_slot(control, "create:shaft")
        distribute(control, shaft_slot, (100,))
        control.call("click-slot", shaft_slot)
        distribute(control, 5, (101, 102))
        craft(control, "create:large_cogwheel", 1)
    print("Survival crafting produced 3 alloys, 8 shafts, and both cogwheels. Casing used one alloy.")


def chassis_conversions(args):
    primary = "create:linear_chassis"
    secondary = "create:secondary_linear_chassis"
    with fixture_world(args, "Chassis-conversions", render=True, pack=args.pack) as control:
        control.commands((
            "/gamemode survival",
            f"/item replace entity @s hotbar.0 with {primary}",
        ))
        control.call("wait", 3)
        control.call("open-inventory")
        for source, target in ((primary, secondary), (secondary, primary)):
            distribute(control, inventory_slot(control, source), (100,))
            craft(control, target, 1)
            counts = control.call("inventory")["counts"]
            if counts.get(target) != 1 or counts.get(source, 0):
                raise RuntimeError(f"Converting {source} to {target} left {counts}.")
    print("Both original shapeless 1:1 chassis conversions worked in the survival player crafting grid.")


def belt_connector(args):
    table = (9, 95, -9)
    with fixture_world(args, "Belt-connector-crafting", STRUCTURE, render=True, pack=args.pack) as control:
        control.commands((
            "/fill 5 94 -12 13 94 -4 minecraft:smooth_stone",
            f"/setblock {' '.join(map(str, table))} minecraft:crafting_table",
            "/tp @s 7.5 95 -9.5",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with minecraft:dried_kelp 6",
        ))
        control.call("interact", *table, "up")
        distribute(control, inventory_slot(control, "minecraft:dried_kelp"), (100, 101, 102, 103, 104, 105))
        craft(control, "create:belt_connector", 1)
        counts = control.call("inventory")["counts"]
        if counts.get("minecraft:dried_kelp", 0) != 0 or counts.get("create:belt_connector") != 1:
            raise RuntimeError(f"Belt Connector crafting left unexpected inventory: {counts}")
    print("Survival crafting consumed six dried kelp and produced the Belt Connector.")


def flywheel(args):
    """Craft and place the original eight-brass-ingot Flywheel recipe."""
    table = (9, 95, -9)
    with fixture_world(args, "Flywheel-crafting", STRUCTURE, render=True, pack=args.pack) as control:
        control.commands((
            "/fill 5 94 -12 13 94 -4 minecraft:smooth_stone",
            f"/setblock {' '.join(map(str, table))} minecraft:crafting_table",
            "/tp @s 7.5 95 -9.5",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:brass_ingot 8",
            "/item replace entity @s hotbar.1 with create:shaft 1",
        ))
        control.call("interact", *table, "up")
        distribute(control, inventory_slot(control, "create:brass_ingot"), (100, 101, 102, 103, 105, 106, 107, 108))
        distribute(control, inventory_slot(control, "create:shaft"), (104,))
        output(control, "create:flywheel", 1)
        before = control.call("inventory")["counts"]
        if before.get("create:brass_ingot", 0) != 0 or before.get("create:shaft", 0) != 0:
            raise RuntimeError(f"Flywheel ingredients were not fully placed: {before}")
        craft(control, "create:flywheel", 1)
        after = control.call("inventory")["counts"]
        if after.get("create:flywheel", 0) != 1 or after.get("create:brass_ingot", 0) or after.get("create:shaft", 0):
            raise RuntimeError(f"Flywheel crafting left unexpected inventory: {after}")
        control.call("close")
        control.call("select", "create:flywheel")
        control.call("interact", 9, 94, -10, "up")
        placed = control.call("block", 9, 95, -10)["state"]
        remaining = control.call("inventory")["counts"].get("create:flywheel", 0)
        if placed not in {"create:flywheel[axis=x]", "create:flywheel[axis=y]", "create:flywheel[axis=z]"} or remaining != 0:
            raise RuntimeError(f"Survival Flywheel placement left {placed} and {remaining} item(s)")
    print("Survival crafting consumed eight brass ingots and one shaft, produced one usable Flywheel, and placed it.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--chassis-conversions", action="store_true")
    parser.add_argument("--belt-connector", action="store_true")
    parser.add_argument("--flywheel", action="store_true")
    args = parser.parse_args()
    action = flywheel if args.flywheel else belt_connector if args.belt_connector else chassis_conversions if args.chassis_conversions else run
    action(args)


if __name__ == "__main__":
    main()
