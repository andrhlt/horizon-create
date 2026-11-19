#!/usr/bin/env python3
"""Craft away the same configured Filter and Train Schedule components as Java."""

import argparse
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

crafting = import_module("test-survival-crafting")
snbt = import_module("test-train-schedule-entry").snbt
SAVED = "{Cyclic:1b,Entries:[]}"
COMPONENTS = {
    "create:filter": ('create:filter_items', '[{slot:0,item:{id:"minecraft:diamond",count:1}}]'),
    "create:schedule": ("create:train_schedule", SAVED),
}


def stack_data(control, item):
    reply = control.command("/data get entity @s Inventory")
    inventory = snbt(reply.split("entity data: ", 1)[1])
    stack = next((stack for stack in inventory if stack["id"] == item), None)
    if stack is None:
        raise RuntimeError(f"Missing {item} in server inventory: {inventory}")
    return stack


def observations(stack, component):
    values = stack.get("components", {})
    return tuple(key in values for key in ("minecraft:custom_name", "minecraft:custom_data", component))


def replay(control, row):
    recipe = row["recipe"]
    item = "create:" + recipe.rsplit("/", 1)[1].removesuffix("_clear")
    component, value = COMPONENTS[item]
    control.command("/clear @s")
    control.command(
        '/data merge block 12 170 24 {Items:[{Slot:0b,id:"' + item
        + '",count:1,components:{"minecraft:custom_name":"Configured part",'
        + f'"minecraft:custom_data":{SAVED},"{component}":{value}'
        + "}}]}"
    )
    control.call("wait", 3)
    control.call("interact", 12, 170, 24, "up")
    menu = control.call("menu")
    stack = next((slot["stack"] for slot in menu["slots"] if slot["slot"] == 300), None)
    if stack is None or stack["item"] != item:
        raise RuntimeError(f"Expected configured {item} in the barrel, found {stack}.")
    control.call("click-slot", 300)
    control.call("click-slot", 0)
    control.call("close")
    control.call("wait", 3)
    configured = stack_data(control, item)
    if observations(configured, component) != (True, True, True):
        raise RuntimeError(f"The configured {item} did not retain the reference components: {configured}")

    control.call("interact", 13, 170, 24, "up")
    crafting.distribute(control, crafting.inventory_slot(control, item), (100,))
    count = int(row["count"])
    crafting.craft(control, item, count)
    control.call("close")
    control.call("wait", 3)
    final = stack_data(control, item)
    expected = tuple(row[column] == "true" for column in ("custom_name", "custom_data", "create_component"))
    if observations(final, component) != expected or final["count"] != count:
        raise RuntimeError(f"{recipe} left {final}, expected count {count} and component presence {expected}.")
    if control.call("inventory")["counts"] != {item: count} or int(row["remainder_stacks"]) != 0:
        raise RuntimeError(f"{recipe} produced unexpected crafting remainders.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with (ROOT / "fixtures/crafting-reset-java.csv").open(newline="") as source:
        reference = list(csv.DictReader(source))
    with fixture_world(args, "Crafting-reset", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:barrel",
            "/setblock 13 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))
        for row in reference:
            replay(control, row)
    print("Both survival crafting resets matched Java stack counts and component removal.")


if __name__ == "__main__":
    main()
