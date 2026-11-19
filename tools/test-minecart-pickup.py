#!/usr/bin/env python3
"""Pick up and replace simple Minecart Contraptions with a Wrench."""
import argparse
from pathlib import Path

from fixture_world import fixture_world


def run_case(args, block, backwards=False):
    with fixture_world(args, "Minecart-pickup", pack=args.pack, render=True) as world:
        orientation = "EAST" if backwards else "WEST"
        block_id = block.split("[", 1)[0]
        placed = block
        if block_id == "minecraft:chest":
            placed += '{Items:[{Slot:0b,count:7,id:"minecraft:copper_ingot"}]}'
        world.commands((
            "/fill 4 169 20 16 169 28 minecraft:stone",
            f"/setblock 8 170 24 create:cart_assembler[shape=east_west,rail_type=regular,backwards={str(backwards).lower()}]",
            f"/setblock 8 171 24 {placed}",
            "/setblock 8 170 25 minecraft:redstone_block",
            "/setblock 10 170 24 minecraft:rail[shape=north_south]",
            "/setblock 12 170 24 minecraft:rail[shape=north_south]",
            "/setblock 14 170 24 create:cart_assembler[shape=east_west,rail_type=regular]",
            '/summon minecraft:minecart 8.5 170.0625 24.5 {Tags:["pickup_fixture"]}',
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:wrench",
            "/tp @s 8.5 170 21.5",
        ))
        for _ in range(30):
            world.step_to(world.clock() + 1)
            marker = world.command("/data get entity @e[type=minecraft:marker,tag=create_cart_payload,limit=1] CreateCartPayload")
            if "create:minecart_anchor" in marker:
                break
        else:
            raise RuntimeError(f"Cart did not assemble: {marker}")
        world.command("/tp @e[type=minecraft:minecart,tag=pickup_fixture,limit=1] 10.5 170.0625 24.5")
        for _ in range(8):
            world.step_to(world.clock() + 1)
        world.command("/tp @s 10.5 170 22.5")
        world.call("key", "1", "tap")
        world.call("look-at", 10.5, 170.2, 24.5)
        world.call("wait", 4)
        world.call("mouse", "right", "click")
        world.call("wait", 3)
        inventory = world.command("/data get entity @s Inventory")
        if block_id == "minecraft:chest":
            cargo = world.command("/data get entity @e[type=minecraft:marker,tag=create_cart_payload,limit=1] CreateCartPayload")
            cart = world.command("/execute if entity @e[type=minecraft:minecart,tag=pickup_fixture]")
            if "create:minecart_contraption" in inventory or "Test passed" not in cart or "minecraft:copper_ingot" not in cargo or "count: 7" not in cargo:
                raise RuntimeError(f"Unsupported cargo was not retained: {inventory}; {cart}; {cargo}")
            print("Loaded chest remains mounted with its seven copper ingots.")
            return
        for text in ("create:minecart_contraption", "create:minecart_contraption_data", "Palette", "BlockList", "create:minecart_anchor", block_id):
            if text not in inventory:
                raise RuntimeError(f"Wrench pickup did not preserve {text}: {inventory}")
        if "Anchor: [I; 8, 170, 24]" not in inventory:
            raise RuntimeError(f"Pickup lost the original assembly position: {inventory}")
        if f'InitialOrientation: "{orientation}"' not in inventory:
            raise RuntimeError(f"Pickup lost the original assembly orientation: {inventory}")
        expected_bounds = "BoundsFront: [-1.0f, 0.0f, -1.0f, 2.0f, 2.0f, 2.0f]"
        if expected_bounds not in inventory:
            raise RuntimeError(f"Minecart bounds differ from Java: {inventory}")
        if "Test passed" in world.command("/execute if entity @e[type=minecraft:minecart,tag=pickup_fixture]"):
            raise RuntimeError("The picked-up minecart is still present")
        world.call("mouse", "right", "click")
        world.call("wait", 3)
        inventory = world.command("/data get entity @s Inventory")
        if inventory.count('id: "create:minecart_contraption"') != 1:
            raise RuntimeError(f"A repeated click duplicated the picked-up item: {inventory}")
        world.call("select", "create:minecart_contraption")
        world.command("/tp @s 12.5 170 21.5")
        world.call("look-at", 12.5, 170.05, 24.5)
        world.call("mouse", "right", "click")
        for _ in range(8):
            world.step_to(world.clock() + 1)
        placed = world.command("/data get entity @e[type=minecraft:marker,tag=create_cart_payload,limit=1] CreateCartPayload")
        if "Anchor: [I; 8, 170, 24]" not in placed or f'InitialOrientation: "{orientation}"' not in placed:
            raise RuntimeError(f"Redeployment lost the original assembly position or orientation: {placed}")
        # Picking it up again verifies the original anchor survives the item round trip.
        world.command("/tp @s 12.5 170 22.5")
        world.call("select", "create:wrench")
        world.call("look-at", 12.5, 170.2, 24.5)
        world.call("wait", 4)
        world.call("mouse", "right", "click")
        world.call("wait", 3)
        inventory = world.command("/data get entity @s Inventory")
        if inventory.count('id: "create:minecart_contraption"') != 1 or "Anchor: [I; 8, 170, 24]" not in inventory or f'InitialOrientation: "{orientation}"' not in inventory:
            raise RuntimeError(f"Second pickup duplicated the item or lost the original anchor: {inventory}")
        world.call("select", "create:minecart_contraption")
        world.command("/tp @s 14.5 170 21.5")
        world.call("look-at", 14.5, 170.05, 24.5)
        world.call("mouse", "right", "click")
        for _ in range(30):
            world.step_to(world.clock() + 1)
            if world.call("block", 14, 171, 24)["block"] == block_id:
                break
        else:
            raise RuntimeError("Placed contraption did not disassemble onto the destination assembler")
        if "[" in block and world.call("block", 14, 171, 24)["state"] != block:
            raise RuntimeError(f"The restored block lost its state: {world.call('block', 14, 171, 24)}")
        if world.call("block", 14, 170, 24)["block"] != "create:cart_assembler":
            raise RuntimeError("The minecart anchor replaced the destination assembler")
    print(f"Wrench pickup and placement retained {block} and the Minecart Anchor.")


def run(args):
    for block, backwards in (("minecraft:stone", False), ("minecraft:oak_planks", True), ("minecraft:cobblestone", False), ("minecraft:glass", True), ("minecraft:oak_log[axis=x]", False), ("minecraft:chest", False)):
        run_case(args, block, backwards)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
