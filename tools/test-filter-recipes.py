#!/usr/bin/env python3
"""Craft the original Brass Nugget and two Filter variants in a survival table."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


crafting = import_module("test-survival-crafting")
reset = import_module("test-crafting-reset")
filters = import_module("test-stockpile-switch-filter")
editor = filters.editor
BARREL = (12, 170, 24)
TABLE = (13, 170, 24)
FEET = (12.5, 170, 26.5)
INGREDIENTS = (
    (("create:brass_ingot", (104,)),),
    (("create:brass_nugget", tuple(range(100, 109))),),
    (("create:brass_nugget", (103, 105)), ("minecraft:blue_wool", (104,))),
    (("create:zinc_nugget", (103, 105)), ("minecraft:green_wool", (104,))),
)
CONFIG = {
    "create:attribute_filter": ("create:attribute_filter_whitelist_mode", '"blacklist"'),
    "create:package_filter": ("create:package_address", '"Workshop"'),
}


def stack_data(host, actor, name, item):
    saved = None
    raw = ""

    def received():
        nonlocal saved, raw
        raw = host.command(f"/data get entity {name} Inventory")
        stacks = reset.snbt(raw.split("entity data: ", 1)[1])
        saved = next((stack for stack in stacks if stack["id"] == item), None)
        return saved is not None

    try:
        editor.wait_for(actor, f"the authoritative {item} inventory update", received)
    except RuntimeError as error:
        raise RuntimeError((item, raw, actor.call("inventory")["counts"])) from error
    return saved


def configured_item(host, actor, name, item):
    component, value = CONFIG[item]
    components = ('{"minecraft:custom_name":"Configured part",'
                  f'"minecraft:custom_data":{{marker:7}},"{component}":{value}}}')
    host.command(f'/data merge block {editor.xyz(BARREL)} '
                 f'{{Items:[{{Slot:0b,id:"{item}",count:1,components:{components}}}]}}')
    actor.call("interact", *BARREL, "up")
    editor.wait_for(actor, "the configured filter in the barrel", lambda: any(
        slot["slot"] == 300 and slot.get("stack") and slot["stack"]["item"] == item
        for slot in actor.call("menu").get("slots", [])
    ))
    actor.call("click-slot", 300)
    actor.call("click-slot", 0)
    actor.call("close")
    actor.call("wait", 3)
    editor.wait_for(actor, "the configured filter to enter the player inventory", lambda:
        actor.call("inventory")["counts"].get(item) == 1
    )
    assert reset.observations(stack_data(host, actor, name, item), component) == (True, True, True)
    return ((item, (104,)),)


def replay(host, actor, name, row):
    case, recipe, item, count, named, custom, filter_data, leftovers = row
    case, count = int(case), int(count)
    host.command(f"/clear {name}")
    editor.wait_for(actor, "the grid ingredients to be cleared", lambda: not actor.call("inventory")["counts"])
    if case < len(INGREDIENTS):
        ingredients = INGREDIENTS[case]
        host.commands(f"/item replace entity {name} hotbar.{index} with {part} {len(slots)}"
                      for index, (part, slots) in enumerate(ingredients))
        editor.wait_for(actor, "the original crafting ingredients", lambda: all(
            actor.call("inventory")["counts"].get(part) == len(slots)
            for part, slots in ingredients
        ))
    else:
        ingredients = configured_item(host, actor, name, item)
    actor.call("interact", *TABLE, "up")
    for part, slots in ingredients:
        crafting.distribute(actor, crafting.inventory_slot(actor, part), slots)
    crafting.craft(actor, item, count)
    actor.call("close")
    actor.call("wait", 3)
    editor.wait_for(actor, f"{recipe} to leave only the crafted result", lambda:
        actor.call("inventory")["counts"] == {item: count}
    )
    assert int(leftovers) == 0
    data = stack_data(host, actor, name, item)
    component = CONFIG.get(item, ("create:package_address", None))[0]
    expected = tuple(field == "true" for field in (named, custom, filter_data))
    assert data["count"] == count and reset.observations(data, component) == expected, (recipe, data)


def verify(args, scratch):
    with (ROOT / "fixtures/filter-recipes-java.csv").open(newline="") as data:
        rows = list(csv.reader(data))
    assert len(rows) == 6
    with fixture_world(args, "FilterRecipes", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 8 169 22 16 169 28 minecraft:stone",
            f"/setblock {editor.xyz(BARREL)} minecraft:barrel",
            f"/setblock {editor.xyz(TABLE)} minecraft:crafting_table",
        ))
        with filters.actor_for(host, args, scratch) as (actor, name):
            host.commands((f"/tp {name} {editor.xyz(FEET)}", f"/gamemode survival {name}"))
            editor.wait_for(actor, "the survival crafter to reach the table", lambda:
                tuple(actor.call("state")["player"]["position"][:3]) == FEET
            )
            for row in rows:
                replay(host, actor, name, row)
    who = "Guest" if scratch else "Host"
    print(f"{who} matched six original Brass Nugget, Filter, and configured Filter reset recipes in survival.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-frc-") as scratch:
            verify(args, Path(scratch))
    else:
        verify(args, None)


if __name__ == "__main__":
    main()
