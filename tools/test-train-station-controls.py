#!/usr/bin/env python3
"""Check Train Station controls for valid, invalid and empty train states."""

import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

train = import_module("test-simple-train")
STRUCTURE = Path("gametest/misc/threshold_switch_pulley.nbt")
X, Y, Z = train.STATION
TRACK = (X, Y, Z - 2)
INVALID = (X + 3, Y, Z - 2)


def buttons(actor):
    return {button["label"]: button["enabled"] for button in actor.call("screen")["buttons"]}


def open_station(world, pos):
    x, y, z = pos
    world.command(f"/tp @s {x + .5} {y} {z + 2.5} 180 20")
    world.call("wait", 3)
    world.call("interact", x, y, z, "up")
    world.call("wait", 4)


def run(args):
    with fixture_world(args, "Train-station-controls", STRUCTURE, render=True) as world:
        x, y, z = TRACK
        world.commands((
            f"/fill 2 {Y - 1} -13 24 {Y - 1} -3 minecraft:smooth_stone",
            f"/fill {x - 3} {Y} {z} {x + 14} {Y} {z} create:track[shape=xo]",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:track_station",
            f"/tp @s {x + 2.5} {Y} {z + .5} 90 20",
        ))
        world.call("wait", 3)
        world.call("key", "1", "tap")
        world.call("look-at", x + .5, Y + .06, z + .5)
        world.call("mouse", "right", "click")
        world.call("wait", 3)
        world.command(f"/tp @s {X + .5} {Y} {Z + 2.5} 180 20")
        world.call("wait", 3)
        world.call("interact", X, Y - 1, Z, "up")
        world.call("wait", 4)
        world.step_to(world.clock() + 1)
        if world.call("block", X, Y, Z)["block"] != "create:track_station":
            raise RuntimeError("The valid target did not accept a survival Train Station placement.")
        target = world.command(f"/data get block {X} {Y} {Z} TargetTrack")
        if "[I; 0, 0, -2]" not in target:
            raise RuntimeError(f"The survival station did not retain its selected track target: {target}")

        open_station(world, (X, Y, Z))
        station = buttons(world)
        if not station.get("Create New Train") or "Disassemble Train" in station or "Retrieve Schedule" in station:
            track_state = world.call("block", *TRACK)
            raise RuntimeError(
                f"The idle bound station exposed the wrong controls: {station}; "
                f"station={world.call('block', X, Y, Z)}; track={track_state}; target={target}"
            )
        world.call("click-button", "Create New Train")
        world.call("wait", 4)
        assembly = buttons(world)
        if not assembly.get("Back") or assembly.get("Assemble Train") is not False:
            raise RuntimeError(f"The empty assembly screen exposed an invalid finish control: {assembly}")
        world.call("key", "esc", "tap")
        world.call("wait", 3)

        ix, iy, iz = INVALID
        world.command(f"/setblock {ix} {iy} {iz} create:track_station")
        open_station(world, INVALID)
        invalid = buttons(world)
        if not invalid.get("Station Name") or any(
            label in invalid for label in ("Create New Train", "Disassemble Train", "Retrieve Schedule")
        ):
            raise RuntimeError(f"The unbound station exposed train controls: {invalid}")
    print("Valid idle and unbound Train Station controls matched the gameplay state.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
