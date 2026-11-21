#!/usr/bin/env python3
"""Pick up and redeploy plain blocks and saved vanilla cargo with a Wrench."""
import argparse
import re
from pathlib import Path

from fixture_world import fixture_world


def run_case(args, block, backwards=False):
    with fixture_world(args, "Minecart-pickup", pack=args.pack, render=True) as world:
        orientation = "EAST" if backwards else "WEST"
        block_id = block.split("[", 1)[0]
        placed = block
        if block_id in ("minecraft:chest", "minecraft:barrel"):
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
        if block_id in ("minecraft:chest", "minecraft:barrel"):
            world.command('/data merge block 8 171 24 {CustomName:\'"Cart cargo"\'}')
        original_state = world.call("block", 8, 171, 24)["state"]
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
        if block_id in ("minecraft:chest", "minecraft:barrel"):
            cart_selector = "@e[type=minecraft:minecart,tag=pickup_fixture,limit=1]"
            world.command("/fill 10 170 20 10 170 28 minecraft:rail[shape=north_south]")
            world.command(f"/data merge entity {cart_selector} {{Motion:[0d,0d,0.1d]}}")
            world.step_to(world.clock() + 1)
            def cart_vector(key):
                data = world.command(f"/data get entity {cart_selector} {key}")
                values = re.search(r"\[([^]]+)\]", data)
                if not values:
                    raise RuntimeError(f"Missing cart {key}: {data}")
                return [float(value.strip().removesuffix("d")) for value in values[1].split(",")]

            before = cart_vector("Pos")
            identity = world.command(f"/data get entity {cart_selector} UUID").split("entity data: ")[-1]
            if cart_vector("Motion")[2] <= 0 or before[2] <= 24.5:
                raise RuntimeError("Active reopen fixture did not move forward")
            world.restart()
            if world.command(f"/data get entity {cart_selector} UUID").split("entity data: ")[-1] != identity:
                raise RuntimeError("Moving reopen lost the cart identity")
            # The client can advance simulation before the control socket freezes it.
            # Verify forward operation, rather than asserting a zero-tick reload boundary.
            after = cart_vector("Pos")
            if after[2] < before[2] or cart_vector("Motion")[2] <= 0:
                raise RuntimeError(f"Moving reopen did not retain forward operation: {before} -> {after}")
            print(f"Moving cargo reopen retained cart identity and forward motion: {before} -> {after}")
            payload = world.command("/data get entity @e[type=minecraft:marker,tag=create_cart_payload,limit=1] CreateCartPayload")
            if "minecraft:copper_ingot" not in payload or "count: 7" not in payload:
                raise RuntimeError(f"Moving reopen lost cargo: {payload}")
            world.command(f"/data merge entity {cart_selector} {{Motion:[0d,0d,0d]}}")
            world.command(f"/tp {cart_selector} 10.5 170.0625 24.5")
            world.step_to(world.clock() + 1)
        world.command("/tp @s 10.5 170 22.5")
        world.call("key", "1", "tap")
        world.call("look-at", 10.5, 170.2, 24.5)
        world.call("wait", 4)
        world.call("mouse", "right", "click")
        world.call("wait", 3)
        inventory = world.command("/data get entity @s Inventory")
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
        if block_id in ("minecraft:chest", "minecraft:barrel"):
            if "minecraft:copper_ingot" not in inventory or "count: 7" not in inventory:
                raise RuntimeError(f"Portable chest lost its cargo: {inventory}")
            world.restart()
            inventory = world.command("/data get entity @s Inventory")
            if "minecraft:copper_ingot" not in inventory or "count: 7" not in inventory:
                raise RuntimeError(f"Picked-up reopen lost cargo: {inventory}")
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
        if world.call("block", 14, 171, 24)["state"] != original_state:
            raise RuntimeError(f"The restored block lost its state: {world.call('block', 14, 171, 24)}")
        if block_id in ("minecraft:chest", "minecraft:barrel"):
            cargo = world.command("/data get block 14 171 24")
            if "minecraft:copper_ingot" not in cargo or "count: 7" not in cargo:
                raise RuntimeError(f"Disassembly lost chest contents: {cargo}")
            loose = world.command('/execute if entity @e[type=minecraft:item,nbt={Item:{id:"minecraft:copper_ingot"}}]')
            if "Test passed" in loose:
                raise RuntimeError(f"Portable round trip duplicated loose cargo: {loose}")
        if world.call("block", 14, 170, 24)["block"] != "create:cart_assembler":
            raise RuntimeError("The minecart anchor replaced the destination assembler")
    print(f"Wrench pickup and placement retained {block} and the Minecart Anchor.")


def run(args):
    for block, backwards in (("minecraft:stone", False), ("minecraft:oak_planks", True), ("minecraft:cobblestone", False), ("minecraft:glass", True), ("minecraft:oak_log[axis=x]", False), ("minecraft:chest", False), ("minecraft:barrel", True)):
        run_case(args, block, backwards)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
