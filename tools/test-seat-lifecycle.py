#!/usr/bin/env python3
"""Check occupied-seat removal and colored-seat save/reopen lifecycle."""

import argparse
import re
from pathlib import Path

from fixture_world import fixture_world


def mounted(world, player):
    world.command(f"/scoreboard players set {player} seat_mount 0")
    world.call(
        "command",
        f"/execute store success score {player} seat_mount as {player} on vehicle if entity @s"
    )
    result = world.command(f"/scoreboard players get {player} seat_mount")
    match = re.search(r"\bhas ([01])\b", result)
    if not match:
        raise RuntimeError(f"Could not query whether {player} is mounted: {result}")
    return match[1] == "1"


def run(args):
    at = (9, 171, 21)
    with fixture_world(args, "Seat-Lifecycle", render=False, pack=args.pack) as world:
        world.commands((
            "/fill 6 170 18 13 170 25 minecraft:smooth_stone",
            "/scoreboard objectives add seat_mount dummy",
            "/setblock 9 171 21 create:red_seat[waterlogged=true]",
        ))
        world.call("lan", "open", 0, "commands", "force")
        player = world.call("lan", "status")["host"]
        world.commands((
            f"/gamemode survival {player}",
            f"/tp {player} 9.5 171 23.5",
        ))
        world.call("interact", *at, "up")
        if not mounted(world, player):
            raise RuntimeError("The survival player did not mount the placed Seat.")
        world.command("/setblock 9 171 21 minecraft:air")
        world.step_to(world.clock() + 1)
        if mounted(world, player):
            raise RuntimeError("Removing the occupied Seat left its player mounted.")

        world.command("/setblock 9 171 21 create:blue_seat[waterlogged=true]")
        world.call("save")
        world.restart()
        state = world.call("block", *at)["state"]
        if state != "create:blue_seat[waterlogged=true]":
            raise RuntimeError(f"Saved seat state changed across reopen: {state}")
        if mounted(world, player):
            raise RuntimeError("The player remained mounted after save/reopen.")
    print("Occupied-seat removal ejected its rider; idle blue waterlogged seat survived save/reopen.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ctl", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("client", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("resources", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
