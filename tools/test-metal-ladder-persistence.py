#!/usr/bin/env python3
"""Verify Metal Ladder states and player inventory survive a cold world reopen."""

import argparse
from pathlib import Path

from fixture_world import fixture_world


CASES = {
    "andesite": {
        "states": ((8, 180, 20),),
        "item": "create:andesite_ladder",
    },
    "brass": {
        "states": ((12, 180, 20),),
        "item": "create:brass_ladder",
    },
    "copper": {
        "states": ((16, 179, 20), (16, 180, 20)),
        "item": "create:copper_ladder",
    },
}


def sample(control):
    blocks = {}
    for material, case in CASES.items():
        blocks[material] = tuple(
            control.call("block", *pos)["state"] for pos in case["states"]
        )
    inventory = control.call("inventory")["counts"]
    counts = {case["item"]: inventory.get(case["item"], 0) for case in CASES.values()}
    return blocks, counts


def verify(args):
    with fixture_world(args, "MetalLadderPersistence", render=True, pack=args.pack) as control:
        control.commands((
            "/gamemode survival",
            "/fill 6 178 18 19 182 22 minecraft:air",
            "/setblock 8 180 21 minecraft:stone",
            "/setblock 8 180 20 create:andesite_ladder[facing=north,waterlogged=false]",
            "/setblock 11 180 20 minecraft:stone",
            "/setblock 12 180 20 create:brass_ladder[facing=east,waterlogged=false]",
            "/setblock 16 180 19 minecraft:stone",
            "/setblock 16 180 20 create:copper_ladder[facing=south,waterlogged=false]",
            "/setblock 16 179 20 create:copper_ladder[facing=south,waterlogged=true]",
            "/item replace entity @s inventory.0 with create:andesite_ladder 2",
            "/item replace entity @s inventory.1 with create:brass_ladder 2",
            "/item replace entity @s inventory.2 with create:copper_ladder 2",
        ))
        before = sample(control)
        expected_blocks = {
            "andesite": ("create:andesite_ladder[facing=north,waterlogged=false]",),
            "brass": ("create:brass_ladder[facing=east,waterlogged=false]",),
            "copper": (
                "create:copper_ladder[facing=south,waterlogged=true]",
                "create:copper_ladder[facing=south,waterlogged=false]",
            ),
        }
        expected_counts = {case["item"]: 2 for case in CASES.values()}
        if before != (expected_blocks, expected_counts):
            raise RuntimeError(f"Unexpected ladder fixture before save: {before}")

        control.call("save")
        control.env["HORIZON_STILL"] = "1"
        control.restart()
        after = sample(control)
        if after != before:
            raise RuntimeError(f"Metal Ladders changed across reopen: {before} -> {after}")

        # Breaking the only support cascades the upper ladder; the waterlogged
        # lower block becomes its fluid source as its matching support vanishes.
        control.command("/setblock 16 180 19 minecraft:air")
        upper, lower = CASES["copper"]["states"][1], CASES["copper"]["states"][0]
        if control.call("block", *upper)["block"] != "minecraft:air":
            raise RuntimeError("Copper ladder remained after its only support was removed")
        if control.call("block", *lower)["block"] != "minecraft:water":
            raise RuntimeError("Waterlogged hanging copper ladder did not revert to water")
        counts_after_support_loss = control.call("inventory")["counts"]
        for case in CASES.values():
            item = case["item"]
            if counts_after_support_loss.get(item, 0) != expected_counts[item]:
                raise RuntimeError(f"Neighbor support loss changed {item} inventory unexpectedly")

    print("Three ladder variants retained facing, support, waterlogging and inventory across cold reopen; support loss removed the upper ladder, restored water and preserved counts.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    verify(parser.parse_args())
