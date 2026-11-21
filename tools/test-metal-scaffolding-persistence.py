#!/usr/bin/env python3
"""Check scaffold connections and climbing survive an idle save/reopen."""

import argparse
from pathlib import Path

from fixture_world import fixture_world

MATERIALS = ("andesite", "brass", "copper")
Y = 170


def setup(world):
    world.commands((
        "/fill 7 169 20 15 169 24 minecraft:stone",
        "/fill 8 170 21 8 174 21 create:andesite_scaffolding",
        "/fill 11 170 21 11 174 21 create:brass_scaffolding",
        "/fill 14 170 21 14 174 21 create:copper_scaffolding",
        "/setblock 14 170 21 create:copper_scaffolding[waterlogged=true]",
    ))


def graph(world):
    result = {}
    for index, material in enumerate(MATERIALS):
        x = 8 + index * 3
        for y in range(Y, Y + 5):
            block = world.call("block", x, y, 21)
            if block["block"] != f"create:{material}_scaffolding":
                raise RuntimeError(f"Scaffold missing at {(x, y, 21)}: {block}")
            result[(x, y, 21)] = block["state"]
    return result


def run(args):
    with fixture_world(args, "MetalScaffoldingPersistence", pack=args.pack) as world:
        setup(world)
        before = graph(world)
        world.call("save")
        world.restart()
        after = graph(world)
        if before != after:
            raise RuntimeError(f"Scaffold states changed across save/reopen: {before} -> {after}")

        # The player can climb the restored stack and leave it without being held.
        world.command("/gamemode survival")
        # Face west so walking backward exits the column toward the east.
        world.command("/tp @s 8.5 170 21.5 90 0")
        world.call("script", script="key space down\nwait 12\nkey space up\nwait 2\n")
        climbed = world.call("state")["player"]["position"][1]
        if climbed < 171:
            raise RuntimeError(f"Player did not ascend the restored scaffold: y={climbed}")
        world.call("script", script="key s down\nwait 10\nkey s up\nwait 2\n")
        final = world.call("state")["player"]
        x, y, z = final["position"]
        left_column = x < 8 or x > 9 or z < 21 or z > 22
        if y < 170 or final["velocity"][1] < -0.2 or not left_column:
            raise RuntimeError(f"Player was trapped or falling after leaving scaffolding: {final}")
    print("All three idle scaffold columns retained their block states across save/reopen; the player climbed and exited the restored structure.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    run(parser.parse_args())
