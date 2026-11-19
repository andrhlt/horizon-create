#!/usr/bin/env python3
"""Use a survival player to fuel a captured Blaze Burner."""

import argparse
from pathlib import Path

from fixture_world import fixture_world

STRUCTURE = Path("gametest/processing/brass_mixing.nbt")
BURNER = (6, 97, -9)


def expect(control, heat, remaining):
    state = control.call("block", *BURNER)["state"]
    fuel = control.command("/data get block 6 97 -9 burnTimeRemaining")
    if f"blaze={heat}" not in state or not fuel.endswith(f": {remaining}"):
        raise RuntimeError(f"Expected {heat} and {remaining} ticks, got {state} and {fuel}")


def run(args):
    with fixture_world(args, "Blaze-burner", STRUCTURE, render=False, pack=args.pack) as control:
        control.command("/fill 3 96 -11 8 96 -6 minecraft:smooth_stone")
        control.command("/fill 3 97 -11 8 100 -6 minecraft:air")
        control.command("/setblock 6 97 -9 create:blaze_burner[blaze=smouldering,facing=west]")
        control.command("/tp @s 4.0 97.0 -8.5 -90 20")
        control.call("wait", 3)
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
    print("A survival player heated a Blaze Burner with coal and then superheated it with a Blaze Cake.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
