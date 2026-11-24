#!/usr/bin/env python3
"""Check Rose Quartz Lamp idle and active state across save/reopen."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world

LAMP = (9, 171, 20)
SOURCE = (9, 171, 19)


def state(world):
    block = world.call("block", *LAMP)
    if block["block"] != "create:rose_quartz_lamp":
        raise RuntimeError(f"Rose Quartz Lamp missing at {LAMP}: {block}")
    return dict(re.findall(r"(\w+)=(\w+)", block["state"]))


def setup(world):
    world.commands((
        "/fill 8 170 18 11 170 21 minecraft:stone",
        f"/setblock {LAMP[0]} {LAMP[1]} {LAMP[2]} create:rose_quartz_lamp",
        "/tp @s 9.5 171 23.5",
    ))
    world.call("wait", 2)


def advance(world, ticks):
    for _ in range(ticks):
        world.step_to(world.clock() + 1)


def run(args):
    with fixture_world(args, "Rose-quartz-lamp-reopen", pack=args.pack) as world:
        setup(world)
        idle = state(world)
        expected_idle = {"powered": "false", "powering": "false", "activate": "false"}
        if any(idle.get(key) != value for key, value in expected_idle.items()):
            raise RuntimeError(f"Expected an idle lamp before save, got {idle}")
        world.command("/save-all flush")
        world.restart()
        idle_reopened = state(world)
        if any(idle_reopened.get(key) != value for key, value in expected_idle.items()):
            raise RuntimeError(f"Idle lamp state changed across reopen: {idle} -> {idle_reopened}")
        world.command(f"/setblock {SOURCE[0]} {SOURCE[1]} {SOURCE[2]} minecraft:redstone_block")
        advance(world, 2)
        active = state(world)
        if active.get("powered") != "true" or active.get("powering") != "true":
            raise RuntimeError(f"Redstone source did not latch the lamp before save: {active}")
        if active.get("activate") != "false":
            raise RuntimeError(f"Lamp did not settle at its active output before save: {active}")
        world.command("/save-all flush")
        world.restart()
        reopened = state(world)
        if any(reopened.get(key) != value for key, value in active.items()):
            raise RuntimeError(f"Active lamp state changed across reopen: {active} -> {reopened}")
    print("Idle and latched Rose Quartz Lamp states survived save/reopen; connected output and reset remain covered by the Java-matched gameplay trace.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
