#!/usr/bin/env python3
"""Verify Copycat off-hand material, removal, and zinc stonecutting using real player actions."""

import csv
from importlib import import_module
import re

from fixture_world import ROOT, fixture_world
COPYCAT = import_module("test-copycat")

STONE = import_module("test-stone-palettes")
POS = (8, 170, 23)
DROPS = "@e[type=minecraft:item,x=5,y=168,z=20,dx=6,dy=5,dz=6]"
PICK = "minecraft:netherite_pickaxe"
COUNT = re.compile(r"\bcount: (\d+)")

def cut(control, result):
    item = "create:zinc_ingot"
    control.command("/clear @s")
    COPYCAT.put(control, item)
    control.call("interact", 8, 169, 25, "up")
    control.call("wait", 2)
    control.call("click-slot", 0)
    STONE.wait_for(item, lambda: (control.call("menu").get("carried") or {}).get("item"),
                   lambda carried: carried == item)
    control.call("click-slot", 600)
    recipe = f"create:copycat_{result}_from_ingots_zinc_stonecutting"
    options = STONE.wait_for(recipe, lambda: (control.call("menu").get("info") or {}).get("recipes", []),
                             lambda recipes: recipe in recipes)
    index = options.index(recipe)
    slot = next(node for node in control.call("ui")["widgets"] if node["id"] == "slot-600")
    left, top, _, _ = slot["bounds"]
    control.call("click-at", left + 40 + index % 4 * 16, top - 10 + index // 4 * 18)
    control.call("click-slot", 650, "shift")
    STONE.wait_for(result, lambda: control.call("inventory")["counts"].get(f"create:copycat_{result}"),
                   lambda count: count == 4)
    control.call("close")

def drop_counts(control, items):
    drops = control.call("entities", 12, "minecraft:item")["entities"]
    actual = {}
    for entity in drops:
        item = entity["item"]["item"]
        if item in items:
            actual[item] = actual.get(item, 0) + entity["item"]["count"]
    return actual


def run(args):
    trace = ROOT / "fixtures/copycat-lifecycle-java.csv"
    with trace.open() as source:
        observations = list(csv.DictReader(source))
    with fixture_world(args, "CopycatLifecycle", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 6 168 21 12 168 26 minecraft:stone",
            "/setblock 7 170 23 minecraft:stone",
            "/setblock 8 169 25 minecraft:stonecutter",
        ))
        for placed, removed in zip(observations[::2], observations[1::2], strict=True):
            wrapper, _ = COPYCAT.state_from_java(placed["wrapper"])
            creative = removed["scenario"] == "creative-break"
            control.call("command", "/gamemode survival")
            control.commands((
                f"/kill {DROPS}",
                "/setblock 8 170 23 air",
                "/tp @s 10.5 169 23.5 90 10",
                "/clear @s",
                "/item replace entity @s weapon.offhand with minecraft:oak_log 3",
            ))
            COPYCAT.put(control, wrapper)
            control.call("look-at", 7.99, 170.20, 23.5)
            control.call("wait", 4)
            control.call("mouse", "right", "click")
            control.call("wait", 3)
            assert control.call("block", *POS)["block"] == wrapper
            material = COPYCAT.material_tag(control)
            expected_material = COPYCAT.state_from_java(placed["state"])
            print("PLACED", control.call("block", *POS)["state"], material, flush=True)
            assert material == expected_material
            count = control.call("inventory")["counts"].get("minecraft:oak_log", 0)
            assert count == int(placed["offhand"]), (wrapper, count, placed)
            applied = control.command("/data get block 8 170 23 Item")
            assert int(COUNT.search(applied)[1]) == int(placed["count_or_drops"]), applied
            COPYCAT.put(control, PICK)
            if creative:
                control.command("/gamemode creative")
            control.call("look-at", 8.17 if wrapper.endswith("_panel") else 8.49, 170.095, 23.5)
            control.call("mouse", "left", "down")
            try:
                for _ in range(35):
                    if control.call("block", *POS)["block"] == "minecraft:air":
                        break
                    control.step_to(control.clock() + 1)
                else:
                    raise RuntimeError(f"Could not break {wrapper} in {removed['scenario']}.")
            finally:
                control.call("mouse", "left", "up")
            expected = COPYCAT.expected_inventory(removed["count_or_drops"])
            control.call("wait", 3)
            STONE.wait_for(f"{wrapper} {removed['scenario']} drops {expected}",
                           lambda: drop_counts(control, (wrapper, "minecraft:oak_log")),
                           lambda found: found == expected)
            print(wrapper, removed["scenario"], "matched", flush=True)
        control.command("/gamemode survival")
        control.command("/tp @s 10.5 169 25.5")
        for name in ("panel", "step"):
            cut(control, name)
    print(f"Matched {len(observations)} lifecycle observations and both four-per-zinc stonecutting recipes.")

if __name__ == "__main__":
    run(COPYCAT.parse_args())
