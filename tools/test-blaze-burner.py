#!/usr/bin/env python3
"""Use a survival player to fuel a captured Blaze Burner."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world

STRUCTURE = Path("gametest/processing/brass_mixing.nbt")
BURNER = (6, 97, -9)


def expect(control, heat, remaining):
    state = control.call("block", *BURNER)["state"]
    fuel = control.command("/data get block 6 97 -9 burnTimeRemaining")
    fuel_matches = fuel.endswith(f": {remaining}") or (
        remaining == 0 and "Found no elements matching" in fuel
    )
    if f"blaze={heat}" not in state or not fuel_matches:
        raise RuntimeError(f"Expected {heat} and {remaining} ticks, got {state} and {fuel}")


def expect_saved(control, heat, remaining):
    state = control.call("block", *BURNER)["state"]
    fuel = control.command("/data get block 6 97 -9 burnTimeRemaining")
    match = re.search(r": (\d+)$", fuel)
    if f"blaze={heat}" not in state or not match or not remaining - 100 <= int(match[1]) <= remaining:
        raise RuntimeError(f"Expected saved {heat} fuel near {remaining} ticks, got {state} and {fuel}")


def acquire_and_place(args):
    with fixture_world(args, "Blaze-burner-acquisition", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 3 96 -11 8 96 -6 minecraft:smooth_stone",
            "/fill 3 97 -11 8 100 -6 minecraft:air",
            "/tp @s 4.0 97.0 -8.5 -90 20",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:empty_blaze_burner 1",
            "/summon minecraft:blaze 5.0 97.0 -8.5",
        ))
        blaze = control.call("entities", 4, "minecraft:blaze")["entities"]
        if len(blaze) != 1:
            raise RuntimeError(f"Expected a single nearby Blaze, got {blaze}")
        control.call("select", "create:empty_blaze_burner")
        control.call("interact-entity", blaze[0]["id"])
        if control.call("entities", 4, "minecraft:blaze")["entities"]:
            raise RuntimeError("The survival capture did not remove the Blaze")
        counts = control.call("inventory")["counts"]
        if counts.get("create:blaze_burner", 0) != 1 or counts.get("create:empty_blaze_burner", 0):
            raise RuntimeError(f"Capture did not exchange one empty burner for a filled burner: {counts}")
        control.call("select", "create:blaze_burner")
        control.call("interact", 6, 96, -9, "up")
        placed = control.call("block", 6, 97, -9)
        if placed["block"] != "create:blaze_burner":
            raise RuntimeError(f"The captured burner did not place on the floor: {placed}")
    print("Survival capture consumed the empty burner, produced a filled burner, and placed it.")


def run(args):
    if args.acquisition:
        acquire_and_place(args)
        return

    with fixture_world(args, "Blaze-burner", STRUCTURE, render=False, pack=args.pack) as control:
        control.command("/fill 3 96 -11 8 96 -6 minecraft:smooth_stone")
        control.command("/fill 3 97 -11 8 100 -6 minecraft:air")
        control.command("/setblock 6 97 -9 create:blaze_burner[blaze=smouldering,facing=west]")
        control.command("/tp @s 4.0 97.0 -8.5 -90 20")
        control.call("wait", 3)
        expect(control, "smouldering", 0)
        control.commands((
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with minecraft:coal 1",
            "/item replace entity @s hotbar.1 with create:blaze_cake 1",
        ))
        control.call("select", "minecraft:coal")
        control.call("interact", *BURNER, "west")
        expect(control, "kindled", 1600)
        control.step_to(control.clock() + 1)
        expect(control, "kindled", 1599)
        control.call("select", "create:blaze_cake")
        control.call("interact", *BURNER, "west")
        expect(control, "seething", 3200)
        counts = control.call("inventory")["counts"]
        if counts.get("minecraft:coal", 0) or counts.get("create:blaze_cake", 0):
            raise RuntimeError(f"Feeding the burner did not consume both fuels: {counts}")
        control.commands((
            "/item replace entity @s hotbar.0 with minecraft:iron_ingot 1",
            "/setblock 6 97 -9 create:blaze_burner[blaze=kindled,facing=west]",
            "/data merge block 6 97 -9 {fuelLevel:1,burnTimeRemaining:9000}",
        ))
        control.call("select", "minecraft:iron_ingot")
        before = control.call("inventory")["counts"].get("minecraft:iron_ingot", 0)
        control.call("interact", *BURNER, "west")
        after = control.call("inventory")["counts"].get("minecraft:iron_ingot", 0)
        expect(control, "kindled", 9000)
        if before != after:
            raise RuntimeError(f"Invalid fuel was consumed: iron ingot count {before} -> {after}")
        control.command("/item replace entity @s hotbar.0 with minecraft:coal 1")
        control.call("wait", 1)
        control.call("select", "minecraft:coal")
        control.call("interact", *BURNER, "west")
        expect(control, "kindled", 10000)
        control.command("/item replace entity @s hotbar.0 with minecraft:coal 1")
        control.command("/data merge block 6 97 -9 {fuelLevel:1,burnTimeRemaining:500}")
        control.call("wait", 1)
        control.call("select", "minecraft:coal")
        control.call("interact", *BURNER, "west")
        expect(control, "kindled", 2100)
        control.commands((
            "/data merge block 6 97 -9 {fuelLevel:1,burnTimeRemaining:1}",
            "/tick step 1",
        ))
        control.call("wait", 1)
        expect(control, "smouldering", 0)
        control.command("/item replace entity @s hotbar.0 with minecraft:lava_bucket 1")
        control.call("wait", 1)
        control.call("select", "minecraft:lava_bucket")
        control.call("interact", *BURNER, "west")
        expect(control, "kindled", 20000)
        counts = control.call("inventory")["counts"]
        if counts.get("minecraft:lava_bucket", 0) or counts.get("minecraft:bucket", 0) != 1:
            raise RuntimeError(f"Lava bucket fuel did not return its crafting remainder: {counts}")

    with fixture_world(args, "Blaze-burner-reopen", STRUCTURE, render=False, pack=args.pack) as control:
        control.command("/fill 3 96 -11 8 96 -6 minecraft:smooth_stone")
        control.command("/fill 3 97 -11 8 100 -6 minecraft:air")
        control.command("/setblock 6 97 -9 create:blaze_burner[blaze=smouldering,facing=west]")
        control.command("/tp @s 4.0 97.0 -8.5 -90 20")
        control.call("wait", 3)
        expect(control, "smouldering", 0)
        control.call("save")
        control.restart()
        expect(control, "smouldering", 0)
        control.commands((
            "/setblock 6 97 -9 create:blaze_burner[blaze=seething,facing=west]",
            "/data merge block 6 97 -9 {fuelLevel:2,burnTimeRemaining:3200}",
        ))
        control.call("save")
        control.restart()
        expect_saved(control, "seething", 3200)
    print("Coal/cake, invalid-fuel rejection, refuel boundaries, expiry, lava-bucket remainder, and idle/active save-reopen passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--acquisition", action="store_true")
    run(parser.parse_args())
