#!/usr/bin/env python3
"""Check idle and powered Nixie Tube text/color across world reopen."""

import argparse
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

TUBE = (8, 120, -8)
TEXT_TUBE = (9, 120, -8)
POWER = (7, 120, -8)
BLOCK = "create:purple_nixie_tube[double_face=floor,facing=east,waterlogged=false]"


def pos(at):
    return " ".join(map(str, at))


def advance(world, ticks):
    for _ in range(ticks):
        world.step_to(world.clock() + 1)


def read_tube(world, expected_power):
    block = world.call("block", *TUBE)
    assert block["block"] == "create:purple_nixie_tube", block
    assert "double_face=floor" in block["state"] and "facing=east" in block["state"], block
    data = world.command(f"/data get block {pos(TUBE)}")
    strength = re.search(r"RedstoneStrength: (\d+)", data)
    actual_power = int(strength[1]) if strength else 0
    assert actual_power == expected_power, (expected_power, data)
    text_block = world.call("block", *TEXT_TUBE)
    text_data = world.command(f"/data get block {pos(TEXT_TUBE)}")
    assert text_block["block"] == "create:purple_nixie_tube", text_block
    assert "PARITY" in text_data and re.search(r"CustomTextIndex: 1\b", text_data), text_data


def run(args):
    with fixture_world(args, "NixiePersistence", pack=args.pack) as world:
        world.commands((
            f"/setblock {pos(TUBE)} {BLOCK}",
            f"/setblock {pos(TEXT_TUBE)} {BLOCK}",
            f"/data merge block {pos(TEXT_TUBE)} {{RawCustomText:'\"PARITY\"',CustomText:'\"PARITY\"',CustomTextIndex:1}}",
        ))
        advance(world, 1)
        read_tube(world, 0)
        world.command("/save-all flush")
        world.restart()
        read_tube(world, 0)
        print("Idle reopen retained the dyed block, mount, and custom text.", flush=True)

        world.command(f"/setblock {pos(POWER)} minecraft:redstone_block")
        advance(world, 2)
        read_tube(world, 15)
        world.command("/save-all flush")
        world.restart()
        read_tube(world, 15)
        world.command(f"/setblock {pos(POWER)} minecraft:air")
        advance(world, 2)
        read_tube(world, 0)
    print("Powered reopen retained strength and text; removing power resumed the Nixie's redstone output.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=lambda path: Path(path).resolve(strict=True),
                        default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
