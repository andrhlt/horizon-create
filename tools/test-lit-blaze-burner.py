#!/usr/bin/env python3
"""Ignite, change and extinguish an empty Blaze Burner."""

import argparse
from pathlib import Path
from fixture_world import fixture_world

STRUCTURE = Path("gametest/processing/brass_mixing.nbt")
BURNER = (6, 97, -9)
WIRE = (8, 97, -9)


def expect(control, value):
    state = control.call("block", *BURNER)["state"]
    if value not in state:
        raise RuntimeError(f"Expected {value}, got {state}")


def outputs(control, power, passive_heat):
    start = control.clock()
    for tick in range(1, 16):
        control.step_to(start + tick)
    wire = control.call("block", *WIRE)["state"]
    assert f"power={power}" in wire, wire
    boiler = control.command("/data get block 6 98 -9")
    assert f"PassiveHeat: {int(passive_heat)}b" in boiler, boiler


def run(args):
    with fixture_world(args, "Lit-blaze-burner", STRUCTURE, render=False, pack=args.pack) as control:
        control.commands((
            "/fill 3 96 -11 8 96 -6 minecraft:smooth_stone",
            "/fill 3 97 -11 8 100 -6 minecraft:air",
            "/setblock 6 97 -9 create:blaze_burner[blaze=none,facing=west]",
            "/setblock 6 98 -9 create:fluid_tank",
            "/setblock 6 99 -9 create:steam_whistle[facing=north,powered=false,size=medium,wall=false]",
            "/setblock 7 97 -9 minecraft:comparator[facing=west]",
            "/setblock 8 97 -9 minecraft:redstone_wire",
            "/tp @s 4.0 97.0 -8.5 -90 20",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with minecraft:flint_and_steel 1",
            "/item replace entity @s hotbar.1 with minecraft:soul_sand 1",
            "/item replace entity @s hotbar.2 with minecraft:iron_shovel 1",
        ))
        control.call("wait", 3)
        control.call("select", "minecraft:flint_and_steel")
        control.call("interact", *BURNER, "west")
        expect(control, "create:lit_blaze_burner[flame_type=regular]")
        outputs(control, 1, True)
        control.call("select", "minecraft:soul_sand")
        before = control.call("inventory")["counts"].get("minecraft:soul_sand", 0)
        control.call("interact", *BURNER, "west")
        expect(control, "create:lit_blaze_burner[flame_type=soul]")
        outputs(control, 2, True)
        after = control.call("inventory")["counts"].get("minecraft:soul_sand", 0)
        if before != after:
            raise RuntimeError(f"Soul sand count changed from {before} to {after}; neighbors={[control.call('block', *at) for at in [(5,97,-9), (7,97,-9), (6,98,-9), (6,97,-8), (6,97,-10)]]}")
        control.call("select", "minecraft:iron_shovel")
        control.call("interact", *BURNER, "west")
        expect(control, "blaze=none")
        outputs(control, 0, False)
    print("Ignited an empty burner, changed its flame with soul sand, and extinguished it. Comparator and passive boiler heat passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
