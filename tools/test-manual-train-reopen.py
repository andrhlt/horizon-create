#!/usr/bin/env python3
"""Check stopped and moving manual trains across save and reopen."""

import argparse
import re
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

train = import_module("test-simple-train")
ENTITY = train.ENTITY
NUMBER = train.NUMBER


def snapshot(world):
    speed, distance, wheels = world.commands(
        f"/data get entity {ENTITY} CreateTrain.{key}"
        for key in ("Speed", "Distance", "WheelPoints")
    )
    wheel_values = tuple(float(value) for value in re.findall(f"({NUMBER})d", wheels))
    if len(wheel_values) != 4:
        raise RuntimeError(f"Expected four saved wheel positions, got {wheels}")
    return float(re.search(f"({NUMBER})d$", speed)[1]), float(re.search(f"({NUMBER})d$", distance)[1]), wheel_values


def drive(world, key, ticks):
    world.call("key", key, "down")
    for _ in range(ticks):
        world.step_to(world.clock() + 1)
    world.call("key", key, "up")


def run(args):
    with fixture_world(args, "Manual-train-reopen", train.STRUCTURE, render=True, pack=args.pack) as world:
        train.setup(world, take_controls=False)
        idle_before = snapshot(world)
        if idle_before[0] != 0:
            raise RuntimeError(f"Newly assembled train should be stopped: {idle_before}")
        world.call("save")
        world.restart()
        idle_after = snapshot(world)
        if idle_after != idle_before:
            raise RuntimeError(f"Stopped train changed over reopen: {idle_before} -> {idle_after}")

        x, y, z = train.X + 1, train.Y + 3, train.Z
        world.command("/attribute @s minecraft:movement_speed base set 0")
        world.command(f"/tp @s {x + 0.5} {y - 3} {z - 1.3} 0 20")
        world.call("wait", 3)
        world.call("look-at", x + 0.5, y + 0.45, z + 0.5)
        world.call("mouse", "right", "click")
        world.call("wait", 3)
        drive(world, "w", 12)
        moving_before = snapshot(world)
        if moving_before[0] <= 0 or moving_before[1] <= idle_after[1]:
            raise RuntimeError(f"Train did not reach moving state before save: {moving_before}")
        world.call("save")
        world.restart()
        moving_after = snapshot(world)
        travelled_after_reopen = moving_after[1] > moving_before[1]
        if not travelled_after_reopen:
            raise RuntimeError(f"Active train did not resume after reopen: {moving_before} -> {moving_after}")
        before_offsets = tuple(point - moving_before[2][0] for point in moving_before[2])
        after_offsets = tuple(point - moving_after[2][0] for point in moving_after[2])
        if any(abs(before - after) > 1e-6 for before, after in zip(before_offsets, after_offsets, strict=True)):
            raise RuntimeError(f"Reopened train wheel spacing changed: {moving_before} -> {moving_after}")
        x, y, z = train.X + 1, train.Y + 3, train.Z
        world.command(f"/tp @s {x + 0.5} {y - 3} {z - 1.3} 0 20")
        world.call("wait", 3)
        data = world.command(f"/data get entity {ENTITY} CreateTrain")
        current_uuid = world.command("/data get entity @s UUID").partition("data: ")[2]
        owner = re.search(r"Driver: (\[I;[^\]]+\])", data)
        if owner is None or owner[1] != current_uuid:
            world.call("look-at", x + 0.5, y + 0.45, z + 0.5)
            world.call("mouse", "right", "click")
            world.call("wait", 3)
        drive(world, "s", 4)
        after = snapshot(world)
        if after[1] >= moving_after[1]:
            raise RuntimeError(f"Reopened train could not be driven in reverse: {moving_after} -> {after}")
    print("Stopped and moving manual trains retained their state through reopen and accepted resumed control.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
