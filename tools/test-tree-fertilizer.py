#!/usr/bin/env python3
"""Exercise the original Tree Fertilizer recipe and simulated growth in survival."""
import argparse
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

crafting = import_module("test-survival-crafting")
multiplayer = import_module("test-multiplayer")
ITEM = "create:tree_fertilizer"


def check_obstructed_tree(world, expected):
    world.commands((
        "/fill 6 169 20 14 169 28 minecraft:dirt",
        "/fill 6 170 20 14 185 28 minecraft:air",
        "/tp @s 10.5 170 25.5",
        "/gamemode survival",
        "/setblock 10 170 22 minecraft:oak_sapling[stage=0]",
        "/setblock 10 171 22 minecraft:stone",
        "/setblock 10 172 22 minecraft:bedrock",
        f"/item replace entity @s hotbar.0 with {ITEM} 2",
    ))
    multiplayer.until("the fertilizer to reach the player", lambda:
                      multiplayer.count(world, ITEM) == 2)
    world.call("select", ITEM)
    world.call("look-at", 10.5, 170.35, 22.5)
    multiplayer.until("the player to target the sapling", lambda:
                      (world.call("looking-at").get("block") or {}).get("pos") == [10, 170, 22])
    world.call("mouse", "right", "click")
    world.call("wait", 4)
    assert world.call("block", 10, 170, 22)["block"] == "minecraft:oak_log"
    assert ((world.call("block", 10, 171, 22)["block"] == "minecraft:oak_log")
            == (expected["trunk_y1_oak_log"] == "true"))
    assert ((world.call("block", 10, 172, 22)["block"] == "minecraft:bedrock")
            == (expected["bedrock_y2_preserved"] == "true"))
    assert multiplayer.count(world, ITEM) == int(expected["remaining"])
    print("One Tree Fertilizer grew the oak through Stone and left Bedrock in place.")


def check_spruce_cluster(world, expected):
    bases = [(x, 170, z) for x in (9, 10) for z in (23, 24)]
    world.commands((
        "/fill 5 169 18 15 169 28 minecraft:dirt",
        "/fill 5 170 18 15 199 28 minecraft:air",
        "/tp @s 10.5 170 27.5",
        f"/item replace entity @s hotbar.0 with {ITEM} 2",
        *(f"/setblock {x} {y} {z} minecraft:spruce_sapling[stage=0]" for x, y, z in bases),
    ))
    multiplayer.until("the player to hold two fertilizer", lambda: multiplayer.count(world, ITEM) == 2)
    world.call("select", ITEM)
    world.call("look-at", 10.5, 170.35, 24.5)
    multiplayer.until("the player to target the spruce", lambda:
                      (world.call("looking-at").get("block") or {}).get("pos") == [10, 170, 24])
    world.call("mouse", "right", "click")
    world.call("wait", 4)
    states = [world.call("block", *at)["block"] for at in bases]
    assert states.count("minecraft:spruce_log") == int(expected["spruce_base_logs"]), states
    assert multiplayer.count(world, ITEM) == int(expected["remaining"])
    soil = world.call("blocks", 5, 169, 18, 15, 169, 28)["blocks"]
    podzol = sum(state.startswith("minecraft:podzol") for *_, state in soil)
    assert podzol == int(expected["podzol_count"]), soil
    print("One Tree Fertilizer grew all four spruce logs and left the soil without podzol.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--recipe-only", action="store_true")
    parser.add_argument("--obstacles", action="store_true")
    args = parser.parse_args()
    with fixture_world(args, "TreeFertilizer", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        if args.obstacles:
            with (ROOT / "fixtures/tree_fertilizer_obstructions-java.csv").open() as source:
                rows = {row["case"]: row for row in csv.DictReader(source)}
            check_obstructed_tree(world, rows["combined"])
            check_spruce_cluster(world, rows["spruce_2x2"])
            return
        world.commands((
            "/fill 6 169 20 14 169 28 minecraft:dirt",
            "/fill 6 170 20 14 185 28 minecraft:air",
            "/tp @s 10.5 170 25.5",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with minecraft:dandelion 2",
            "/item replace entity @s hotbar.1 with minecraft:horn_coral",
            "/item replace entity @s hotbar.2 with minecraft:bone_meal",
        ))
        world.call("open-inventory")
        for item, slots in (("minecraft:dandelion", (100, 101)),
                            ("minecraft:horn_coral", (102,)),
                            ("minecraft:bone_meal", (103,))):
            crafting.distribute(world, crafting.inventory_slot(world, item), slots)
        crafting.craft(world, ITEM, 2)
        counts = world.call("inventory")["counts"]
        assert all(not counts.get(item, 0) for item in
                   ("minecraft:dandelion", "minecraft:horn_coral", "minecraft:bone_meal")), counts
        world.call("close")
        if args.recipe_only:
            print("Survival recipe yielded two and consumed its four ingredients.", flush=True)
            return
        world.command(f"/item replace entity @s hotbar.0 with {ITEM} 64")
        world.call("select", ITEM)
        world.commands((
            "/setblock 10 170 23 minecraft:stone",
        ))
        before = world.call("inventory")["counts"][ITEM]
        world.call("interact", 10, 170, 23, "up")
        assert world.call("block", 10, 170, 23)["state"] == "minecraft:stone"
        assert world.call("inventory")["counts"][ITEM] == before
        world.commands(("/setblock 10 170 23 minecraft:air",
                        "/setblock 10 170 22 minecraft:oak_sapling[stage=1]"))
        world.call("interact", 10, 170, 22, "up")
        multiplayer.until("the oak to grow after one application", lambda:
                          world.call("block", 10, 170, 22)["block"] == "minecraft:oak_log")
        assert multiplayer.count(world, ITEM) == before - 1
        world.commands((
            "/fill 6 170 20 14 185 28 minecraft:air",
            "/setblock 10 170 22 minecraft:oak_sapling[stage=1]",
            "/item replace entity @s hotbar.0 with minecraft:bone_meal 64",
        ))
        world.call("select", "minecraft:bone_meal")
        for bone_attempts in range(1, 33):
            world.call("interact", 10, 170, 22, "up")
            if world.call("block", 10, 170, 22)["state"].startswith("minecraft:oak_log"):
                break
        else:
            raise AssertionError("Ordinary bone meal did not grow oak")
        print(f"Survival recipe yielded two; stone was rejected; oak grew with one fertilizer; ordinary bone meal took {bone_attempts} applications.", flush=True)


if __name__ == "__main__":
    main()
