#!/usr/bin/env python3
"""Check empty-input, full-output, and redstone stop/resume arm behavior."""

import argparse
import re
from pathlib import Path

from fixture_world import fixture_world

ARM = (0, 97, 0)
SOURCE = (0, 97, -2)
DESTINATION = (0, 97, 2)
POINTS = (
    '{Type:"minecraft:barrel",Pos:[I;0,0,-2],Mode:"TAKE"},'
    '{Type:"minecraft:barrel",Pos:[I;0,0,2],Mode:"DEPOSIT"}'
)


def item_count(text, item):
    total = 0
    for stack in re.findall(r"\{([^{}]*)\}", text):
        identity = re.search(r'\bid: "([\w:]+)"', stack)
        count = re.search(r"\b(?:Count|count): (\d+)", stack)
        if identity and identity[1] == item and count:
            total += int(count[1])
    return total


def contents(control, pos):
    return control.command(f"/data get block {' '.join(map(str, pos))} Items")


def advance(control, ticks):
    end = control.clock() + ticks
    for tick in range(control.clock() + 1, end + 1):
        control.step_to(tick)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()

    with fixture_world(args, "ArmBackpressure", pack=args.pack) as control:
        control.commands((
            "/fill -4 96 -5 4 96 5 minecraft:smooth_stone",
            "/fill -4 97 -5 4 102 5 minecraft:air",
            "/setblock 0 96 0 create:creative_motor[facing=up]",
            "/data merge block 0 96 0 {ScrollValue:64}",
            "/setblock 0 97 -2 minecraft:barrel",
            "/setblock 0 97 2 minecraft:barrel",
            "/setblock 0 97 0 create:mechanical_arm",
            f"/data merge block 0 97 0 {{InteractionPoints:[{POINTS}]}}",
        ))

        # An empty configured source must leave the arm idle.
        advance(control, 24)
        source = contents(control, SOURCE)
        if "[]" not in source:
            raise RuntimeError(f"The empty source unexpectedly gained items: {source}")
        if "HeldItem: {}" not in control.command(f"/data get block {' '.join(map(str, ARM))}"):
            raise RuntimeError("The arm should remain empty while its input is unavailable")

        # A full destination blocks extraction without losing source contents.
        control.commands((
            *(f"/item replace block 0 97 2 container.{slot} with minecraft:iron_ingot 64"
              for slot in range(27)),
            "/item replace block 0 97 -2 container.0 with minecraft:iron_ingot 1",
        ))
        advance(control, 32)
        source = contents(control, SOURCE)
        destination = contents(control, DESTINATION)
        if (item_count(source, "minecraft:iron_ingot") != 1
                or item_count(destination, "minecraft:iron_ingot") != 27 * 64):
            raise RuntimeError(f"Full destination changed inventory custody: {source} / {destination}")
        arm = control.command(f"/data get block {' '.join(map(str, ARM))}")
        if 'Phase: "SEARCH_INPUTS"' not in arm:
            raise RuntimeError(f"Arm should wait safely when output has no capacity: {arm}")

        # After output space opens, redstone must hold the source unchanged.
        control.commands(
            f"/item replace block 0 97 2 container.{slot} with minecraft:air"
            for slot in range(27)
        )
        control.command("/setblock 1 97 0 minecraft:redstone_block")
        advance(control, 32)
        if item_count(contents(control, SOURCE), "minecraft:iron_ingot") != 1:
            raise RuntimeError("Powered arm extracted from an input despite its redstone lock")
        if item_count(contents(control, DESTINATION), "minecraft:iron_ingot") != 0:
            raise RuntimeError("Powered arm deposited an item while it should be stopped")

        control.command("/setblock 1 97 0 minecraft:air")
        advance(control, 64)
        source = contents(control, SOURCE)
        destination = contents(control, DESTINATION)
        arm = control.command(f"/data get block {' '.join(map(str, ARM))}")
        if item_count(source, "minecraft:iron_ingot") != 0 or item_count(destination, "minecraft:iron_ingot") != 1:
            raise RuntimeError(f"Arm did not resume one exact transfer: {source} / {destination}")
        if "HeldItem: {}" not in arm:
            raise RuntimeError(f"Transferred ingot remained stuck in the arm: {arm}")
    print("Mechanical Arm waited on empty/full endpoints, stopped under redstone, and resumed one exact transfer.")


if __name__ == "__main__":
    main()
