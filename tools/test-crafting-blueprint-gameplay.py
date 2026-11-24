#!/usr/bin/env python3
"""Exercise a bounded survival Blueprint place, edit, use and recovery path."""

import argparse
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world
import importlib

crafting = importlib.import_module("test-survival-crafting")
mp_spec = importlib.util.spec_from_file_location(
    "blueprint_multiplayer", Path(__file__).with_name("test-multiplayer.py")
)
multiplayer = importlib.util.module_from_spec(mp_spec)
mp_spec.loader.exec_module(multiplayer)
GUEST = "BlueprintGuest"


def count(world, item):
    return world.call("inventory")["counts"].get(item, 0)


def blueprint(world):
    matches = world.call("entities", 32, "create:blueprint")["entities"]
    if not matches:
        raise RuntimeError("No placed Crafting Blueprint entity was visible")
    return matches[0]


def interact(world, entity, item=None):
    if item:
        world.call("select", item)
    x, y, z = entity["pos"]
    world.call("tp", x, y + 1, z - 3)
    aimed = world.call("look-at-entity", entity["id"])
    target = world.call("looking-at")
    clicked = world.call("mouse", "right", "click")
    world.step_to(world.clock() + 1)
    return aimed, target, clicked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    args = parser.parse_args()

    with fixture_world(args, "CraftingBlueprintGameplay", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.command("/gamemode survival")
        world.commands((
            "/difficulty peaceful",
            "/kill @e[type=!player]",
            "/fill 4 99 -13 8 99 -5 minecraft:smooth_stone",
            "/fill 4 100 -11 8 106 -7 minecraft:air",
            "/item replace entity @s hotbar.0 with minecraft:painting",
            "/item replace entity @s hotbar.1 with minecraft:crafting_table",
        ))
        world.call("open-inventory")
        for index, item in enumerate(("minecraft:painting", "minecraft:crafting_table")):
            crafting.distribute(world, crafting.inventory_slot(world, item), (100 + index,))
        crafting.craft(world, "create:crafting_blueprint", 1)
        world.call("close")
        assert count(world, "create:crafting_blueprint") == 1

        world.call("tp", 6.5, 101, -5.5)
        placed = None
        for _ in range(3):
            world.call("look-at-block", 6, 99, -9, "up")
            hit = world.call("looking-at")
            assert hit["block"]["pos"] == [6, 99, -9] and hit["block"]["face"] == "up", hit
            try:
                world.call("place", 6, 100, -9, "--item", "create:crafting_blueprint")
            except RuntimeError as error:
                # horizon-ctl reports entity placement as unchanged because
                # the target block remains air; verify the entity below.
                if "the block did not change" not in str(error):
                    raise
            matches = world.call("entities", 32, "create:blueprint")["entities"]
            if matches:
                placed = matches[0]
                break
            if count(world, "create:crafting_blueprint") == 0:
                raise RuntimeError("Placement consumed the item but created no Blueprint entity")
        if placed is None:
            raise RuntimeError("Placement did not create a Blueprint after three verified support-face uses")
        assert count(world, "create:crafting_blueprint") == 0
        world.commands((
            "/give @s create:wrench",
            "/give @s minecraft:oak_planks 4",
        ))
        interact(world, placed, "create:wrench")
        configured = world.command("/data get entity @e[type=create:blueprint,limit=1]")
        assert "CreateBlueprintRecipe" in configured, configured
        world.call("save")
        world.restart()
        placed = blueprint(world)
        reopened = world.command("/data get entity @e[type=create:blueprint,limit=1]")
        assert "CreateBlueprintRecipe" in reopened, reopened
        world.call("select", "minecraft:oak_planks")

        before_planks = count(world, "minecraft:oak_planks")
        interact(world, placed)
        after_planks = count(world, "minecraft:oak_planks")
        after_tables = count(world, "minecraft:crafting_table")
        assert before_planks == 4 and after_planks == 0, (before_planks, after_planks)
        assert after_tables == 1, after_tables

        network = world.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-blueprint-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True,
            scenario="blueprint-gameplay", pack=args.pack,
        ) as guest:
            multiplayer.until("Blueprint guest to join", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in world.call("lan", "status")["guests"]
            ))
            for command in (
                f"/gamemode survival {GUEST}",
                f"/give {GUEST} minecraft:oak_planks 4",
                f"/tp {GUEST} 6.5 101 -11.5",
            ):
                world.call("command", command)
            multiplayer.until("guest to receive four planks", lambda:
                              count(guest, "minecraft:oak_planks") == 4)
            guest.call("select", "minecraft:oak_planks")
            guest.call("look-at-entity", placed["id"])
            guest.call("mouse", "right", "click")
            world.step_to(world.clock() + 1)
            multiplayer.until("guest to receive one crafting table", lambda:
                              count(guest, "minecraft:crafting_table") == 1)
            assert count(guest, "minecraft:oak_planks") == 0

        world.call("attack", placed["id"])
        drops = world.call("entities", 32, "minecraft:item")["entities"]
        assert any(
            entity.get("item", {}).get("item") == "create:crafting_blueprint"
            and entity.get("item", {}).get("count") == 1
            for entity in drops
        ), drops
        world.step_to(world.clock() + 1)
        assert not world.call("entities", 32, "create:blueprint")["entities"]

    print("Crafted, placed, configured, used, saved/reopened, and broke a Blueprint; four planks became one Crafting Table and one Blueprint was recovered.")


if __name__ == "__main__":
    main()
