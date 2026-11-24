#!/usr/bin/env python3
"""Check Mechanical Arm idle and held-item save/reopen behavior."""

import argparse
import re
from pathlib import Path

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/brass_mixing_2.nbt")
ARM = (5, 98, -6)
LEVER = "/setblock 6 98 -7 minecraft:lever[face=floor,facing=west,powered={}]"


def block(control, pos):
    return control.command(f"/data get block {' '.join(map(str, pos))}")


def held(control):
    tag = control.command(f"/data get block {' '.join(map(str, ARM))} HeldItem")
    return tag


def count_item(text, item):
    total = 0
    for stack in re.findall(r"\{([^{}]*)\}", text):
        identity = re.search(r'\bid: "([\w:]+)"', stack)
        count = re.search(r"\b(?:Count|count): (\d+)", stack)
        if identity and identity[1] == item and count:
            total += int(count[1])
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()

    with fixture_world(args, "ArmIdleReopen", STRUCTURE, pack=args.pack) as control:
        control.command("/place template create:gametest/processing/brass_mixing_2 3 96 -12")
        control.command(LEVER.format("false"))
        before = block(control, ARM)
        if "InteractionPoints" not in before:
            raise RuntimeError(f"Idle arm has no configured interaction points: {before}")
        control.command("/save-all")
        control.restart()
        after = block(control, ARM)
        if "InteractionPoints" not in after:
            raise RuntimeError(f"Idle arm configuration was lost on reopen: {after}")
        if "HeldItem: {}" not in after and "HeldItem: {}" not in held(control):
            raise RuntimeError(f"Idle arm unexpectedly holds an item after reopen: {after}")

    with fixture_world(args, "ArmHeldReopen", STRUCTURE, pack=args.pack) as control:
        control.command("/place template create:gametest/processing/brass_mixing_2 3 96 -12")
        control.command(LEVER.format("false"))
        start = control.clock()
        for tick in range(1, 33):
            control.step_to(start + tick)
        saved_arm = block(control, ARM)
        saved_item = held(control)
        if 'Phase: "SEARCH_OUTPUTS"' not in saved_arm or "create:zinc_ingot" not in saved_item:
            raise RuntimeError(f"Expected the fixture arm to hold zinc before save: {saved_arm} / {saved_item}")
        if "InteractionPoints" not in saved_arm:
            raise RuntimeError(f"Configured targets missing before save: {saved_arm}")
        control.command("/save-all")
        control.restart()
        reopened_arm = block(control, ARM)
        reopened_item = held(control)
        if count_item(reopened_item, "create:zinc_ingot") != 1:
            raise RuntimeError(f"Held zinc was not retained across reopen: {reopened_item}")
        if "InteractionPoints" not in reopened_arm:
            raise RuntimeError(f"Arm target configuration was not retained: {reopened_arm}")
        for _ in range(30):
            control.step_to(control.clock() + 1)
            basin = control.command("/data get block 6 98 -9 Items")
            if count_item(basin, "create:zinc_ingot"):
                break
        else:
            raise RuntimeError("Reopened arm did not resume transfer of its held zinc into the basin")
        final_item = held(control)
        if count_item(final_item, "create:zinc_ingot"):
            raise RuntimeError(f"Arm still holds the zinc after basin transfer: {final_item}")
    print("Mechanical Arm idle configuration and held-item transfer survived save/reopen.")


if __name__ == "__main__":
    main()
