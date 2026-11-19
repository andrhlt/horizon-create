#!/usr/bin/env python3
"""Check idle and active cogwheel networks survive a world reopen."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world


MOTOR = (4, 101, 5)
INPUT = (5, 101, 5)
LARGE = (6, 101, 5)
SMALL = (6, 102, 6)
OUTPUT = (7, 102, 6)


def speed(world, pos):
    reply = world.command(f"/data get block {' '.join(map(str, pos))} Speed")
    match = re.search(r"(-?\d+(?:\.\d+)?)f\b", reply)
    if not match:
        raise RuntimeError(f"Missing kinetic speed at {pos}: {reply}")
    return float(match[1])


def setup(world):
    world.commands((
        "/fill 2 100 3 9 100 8 minecraft:smooth_stone",
        "/fill 2 101 3 9 104 8 minecraft:air",
        f"/setblock {' '.join(map(str, MOTOR))} create:creative_motor[facing=east]",
        f"/setblock {' '.join(map(str, INPUT))} create:shaft[axis=x]",
        f"/setblock {' '.join(map(str, LARGE))} create:large_cogwheel[axis=x]",
        f"/setblock {' '.join(map(str, SMALL))} create:cogwheel[axis=x]",
        f"/setblock {' '.join(map(str, OUTPUT))} create:shaft[axis=x]",
        f"/data merge block {' '.join(map(str, MOTOR))} {{ScrollValue:0}}",
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()

    with fixture_world(args, "CogwheelReopen", render=False, pack=args.pack) as world:
        setup(world)
        world.step_to(world.clock() + 1)
        positions = (INPUT, LARGE, SMALL, OUTPUT)
        idle_state = tuple(world.call("block", *pos)["state"] for pos in positions)
        idle_speeds = tuple(speed(world, pos) for pos in positions)
        if idle_speeds != (0.0, 0.0, 0.0, 0.0):
            raise RuntimeError(f"Idle cog train unexpectedly moved: {idle_speeds}")
        world.restart()
        if tuple(world.call("block", *pos)["state"] for pos in positions) != idle_state:
            raise RuntimeError("Idle cogwheel or shaft states changed after reopen.")
        if tuple(speed(world, pos) for pos in positions) != idle_speeds:
            raise RuntimeError("Idle cogwheel network speeds changed after reopen.")

        world.command(f"/data merge block {' '.join(map(str, MOTOR))} {{ScrollValue:24}}")
        world.step_to(world.clock() + 1)
        active_speeds = tuple(speed(world, pos) for pos in positions)
        if active_speeds != (24.0, 24.0, -48.0, -48.0):
            raise RuntimeError(f"Active cog train had unexpected gear speeds: {active_speeds}")
        world.restart()
        reopened_speeds = tuple(speed(world, pos) for pos in positions)
        if reopened_speeds != active_speeds:
            raise RuntimeError(f"Active gear ratio did not survive reopen: {active_speeds} -> {reopened_speeds}")
        world.step_to(world.clock() + 1)
        resumed = tuple(speed(world, pos) for pos in positions)
        if resumed != active_speeds:
            raise RuntimeError(f"Active gear train did not resume after reload: {resumed}")

    print("Idle and active large-to-small cog networks retained their blocks and speeds across reopen; active motion resumed.")


if __name__ == "__main__":
    main()
