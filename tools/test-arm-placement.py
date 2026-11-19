#!/usr/bin/env python3
"""Set an arm's two interaction points by hand and move a depot stack."""

import argparse
from pathlib import Path

from fixture_world import fixture_world

STRUCTURE = Path("gametest/processing/brass_mixing_2.nbt")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    args = parser.parse_args()
    with fixture_world(args, "Arm-placement", STRUCTURE, render=True) as control:
        control.command("/fill 2 96 -13 10 96 -5 minecraft:smooth_stone")
        control.command("/fill 2 97 -13 10 102 -5 minecraft:air")
        control.commands((
            "/setblock 6 97 -11 create:depot",
            "/setblock 8 97 -9 create:depot",
            "/setblock 6 97 -9 create:creative_motor[facing=up]",
            "/data merge block 6 97 -9 {ScrollValue:64}",
            "/item replace block 6 97 -11 container.0 with minecraft:iron_ingot",
            "/tp @s 5.1 97 -8.0 180 20",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:mechanical_arm",
        ))
        control.call("wait", 3)
        control.call("select", "create:mechanical_arm")
        control.call("interact", 6, 97, -11, "up")
        control.call("interact", 8, 97, -9, "up")
        control.call("interact", 8, 97, -9, "up")
        control.call("place", 6, 98, -9, "create:mechanical_arm")
        points = control.command("/data get block 6 98 -9 InteractionPoints")
        if points.count('Type: "create:depot"') != 2 or 'Mode: "TAKE"' not in points or 'Mode: "DEPOSIT"' not in points:
            raise RuntimeError(f"The placed arm did not retain both selected points: {points}")
        start = control.clock()
        for tick in range(1, 97):
            control.step_to(start + tick)
            result = control.command("/data get block 8 97 -9 Items")
            if "minecraft:iron_ingot" in result:
                break
        else:
            raise RuntimeError(f"The arm did not move the iron ingot: {result}")
        source = control.command("/data get block 6 97 -11 Items")
        if "minecraft:iron_ingot" in source:
            raise RuntimeError(f"The arm left the iron ingot in its source: {source}")
    print(f"Configured the arm through ordinary clicks and moved the ingot on tick {tick}.")


if __name__ == "__main__":
    main()
