#!/usr/bin/env python3
"""Check a bearing-mounted Mechanical Saw cutting and retaining an oak tree."""

import argparse
from pathlib import Path

from fixture_world import fixture_world


BEARING = (8, 100, 8)
MOTOR = (8, 99, 8)
ANCHOR = (8, 101, 8)
SAW = (10, 101, 8)
TREE = ((11, 101, 8), (11, 102, 8), (11, 103, 8))
LEAF = (11, 104, 8)


def xyz(pos):
    return " ".join(map(str, pos))


def check(args):
    with fixture_world(args, "MechanicalSawBearingTree", pack=args.pack) as control:
        control.commands((
            f"/setblock {xyz(BEARING)} create:mechanical_bearing[facing=up]",
            f"/setblock {xyz(MOTOR)} create:creative_motor[facing=up]{{ScrollValue:0}}",
            f"/setblock {xyz(ANCHOR)} create:linear_chassis[axis=x,sticky_top=true,sticky_bottom=true]",
            "/setblock 7 101 8 minecraft:barrel",
            "/setblock 9 101 8 minecraft:smooth_stone",
            f"/setblock {xyz(SAW)} create:mechanical_saw[facing=east]",
            *(f"/setblock {xyz(pos)} minecraft:oak_log[axis=y]" for pos in TREE),
            f"/setblock {xyz(LEAF)} minecraft:oak_leaves[distance=1,persistent=true]",
            "/tp @s 8.5 101 11.5",
        ))
        control.command(f'/data merge block {xyz(SAW)} {{Filter:{{id:"minecraft:spruce_trapdoor",count:1}}}}')
        control.call("save")
        control.restart()
        idle_saw = control.command(f"/data get block {xyz(SAW)} Filter")
        if "minecraft:spruce_trapdoor" not in idle_saw:
            raise RuntimeError(f"Idle saw filter did not survive save/reopen: {idle_saw}")
        control.command("/tp @s 8.5 101 11.5")
        control.command(f"/data merge block {xyz(MOTOR)} {{ScrollValue:256}}")
        control.command("/item replace entity @s weapon.mainhand with minecraft:air")
        control.call("interact", *BEARING, "south")
        for _ in range(3):
            control.step_to(control.clock() + 1)
        bearing = control.command(f"/data get block {xyz(BEARING)}")
        if "MovedBlocks" not in bearing or "create:mechanical_saw" not in bearing:
            raise RuntimeError(f"Bearing failed to capture the saw assembly: {bearing}")
        for _ in range(12):
            control.step_to(control.clock() + 1)
        control.call("save")
        control.restart()
        reopened = control.command(f"/data get block {xyz(BEARING)}")
        if "MovedBlocks" not in reopened or "Running: 1b" not in reopened:
            raise RuntimeError(f"Active saw assembly did not survive save/reopen: {reopened}")
        for _ in range(160):
            control.step_to(control.clock() + 1)
        remaining = tuple(
            control.command(f"/execute if block {xyz(pos)} minecraft:oak_log")
            for pos in TREE
        )
        if any("Test passed" in result for result in remaining):
            bearing = control.command(f"/data get block {xyz(BEARING)}")
            raise RuntimeError(
                f"Bearing-mounted saw did not cut the representative oak trunk: {remaining}; {bearing}"
            )
        if control.call("block", *LEAF)["block"] != "minecraft:air":
            raise RuntimeError("The moving saw did not clear the representative tree's attached leaves.")
        cargo = control.command(f"/data get block {xyz(BEARING)}")
        if "minecraft:oak_log" not in cargo or "count: 3" not in cargo:
            inventory = control.call("inventory")["counts"]
            loose = control.command(
                '/execute if entity @e[type=minecraft:item,nbt={Item:{id:"minecraft:oak_log"}}]'
            )
            raise RuntimeError(
                f"Cut oak logs were not all retained; tree={remaining}; mounted={cargo}; "
                f"player={inventory}; loose={loose}"
            )
        print(f"Idle filter and active bearing-mounted tree cut survived save/reopen; all three logs were retained: {remaining}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    check(parser.parse_args())
