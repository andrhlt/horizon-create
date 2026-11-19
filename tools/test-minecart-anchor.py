#!/usr/bin/env python3
"""Check the internal cart anchor's axis and its assembly/disassembly lifecycle."""
import argparse
from pathlib import Path
import re

from fixture_world import fixture_world


def run(args):
    with fixture_world(args, "MinecartAnchor", pack=args.pack) as world:
        world.commands((
            "/tp @s 10.5 175 24.5",
            "/fill 4 169 20 28 169 29 minecraft:stone",
        ))
        for x, shape, axis in ((8, "east_west", "x"), (20, "north_south", "z")):
            z = 24
            world.commands((
                f"/setblock {x} 170 {z} create:cart_assembler[shape={shape},rail_type=powered_rail]",
                f"/setblock {x} 171 {z} minecraft:stone",
                f"/setblock {x} 170 {z+1} minecraft:redstone_block",
                f'/summon minecraft:minecart {x+0.5} 170.0625 {z+0.5} {{Tags:["anchor_test"]}}',
            ))
            payload = ""
            for _ in range(30):
                world.step_to(world.clock() + 1)
                payload = world.command("/data get entity @e[type=minecraft:marker,tag=create_cart_payload,limit=1] CreateCartPayload")
                if "create:minecart_anchor" in payload:
                    break
            if not re.search(r'axis: "' + axis + r'".*?Name: "create:minecart_anchor"', payload):
                raise RuntimeError(f"{shape}: expected a mounted anchor with axis {axis}, got {payload}")
            if world.call("block", x, 171, z)["block"] != "minecraft:air":
                raise RuntimeError(f"{shape}: the structure did not assemble")
            world.command(f"/setblock {x} 170 {z+1} minecraft:air")
            for _ in range(30):
                world.step_to(world.clock() + 1)
                if world.call("block", x, 171, z)["block"] == "minecraft:stone":
                    break
            assembler = world.call("block", x, 170, z)["block"]
            cargo = world.call("block", x, 171, z)["block"]
            marker = world.command("/data get entity @e[type=minecraft:marker,tag=create_cart_payload,limit=1] CreateCartPayload")
            if assembler != "create:cart_assembler" or cargo != "minecraft:stone" or "create:minecart_anchor" in marker:
                raise RuntimeError(f"{shape}: disassembly left assembler={assembler}, cargo={cargo}, payload={marker}")
            world.command('/kill @e[type=minecraft:minecart,tag=anchor_test]')
    print("Both Minecart Anchor axes assembled and disassembled without replacing the rail.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
