#!/usr/bin/env python3
"""Check Millstone output backpressure and recovery against pinned Java tick rules."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world

STRUCTURE = Path("gametest/processing/wheat_milling.nbt")
BARREL = "5 102 -11"
MILL = "5 98 -11"
CHUTE = "5 97 -11"
LEVER = "4 102 -11"
OUTPUT_SLOT = 1  # Combined handler slot zero is input; output inventory begins at one.


def block(world, pos):
    return world.command(f"/data get block {pos}")


def scalar(world, key):
    match = re.search(rf"\b{re.escape(key)}: (-?\d+(?:\.\d+)?)f?\b", block(world, MILL))
    if not match:
        raise RuntimeError(f"Millstone NBT did not expose {key}.")
    return float(match[1]) if "." in match[1] else int(match[1])


def count_item(tag, item):
    total = 0
    for stack in re.findall(r'\{([^{}]*\bid: "[a-z0-9_.-]+:[^{}]+)\}', tag):
        found = re.search(r'\bid: "[a-z0-9_.-]+:([^" ]+)"', stack)
        if not found or found[1] != item:
            continue
        count = re.search(r"\b(?:count|Count): (\d+)", stack)
        total += int(count[1]) if count else 1
    return total


def mill_inventory(world):
    nbt = block(world, MILL)
    return count_item(nbt, "wheat"), count_item(nbt, "wheat_flour")


def wait_for(world, predicate, description, ticks=40):
    for _ in range(ticks):
        if predicate():
            return
        world.step_to(world.clock() + 1)
    raise RuntimeError(f"Timed out waiting for {description}.")


def run(args):
    with fixture_world(args, "MillstoneBackpressure", STRUCTURE, pack=args.pack) as world:
        world.command("/place template create:gametest/processing/wheat_milling 3 96 -12")
        world.command(f"/setblock {LEVER} minecraft:lever[face=wall,facing=west,powered=true]")
        world.commands((
            f"/item replace block {BARREL} container.13 with minecraft:air",
            f"/item replace block {BARREL} container.0 with minecraft:air",
            f"/setblock {CHUTE} minecraft:air",
            f"/item replace block {MILL} container.0 with minecraft:wheat 1",
            f"/item replace block {MILL} container.{OUTPUT_SLOT} with create:wheat_flour 64",
        ))

        world.step_to(world.clock() + 1)
        if scalar(world, "Speed") == 0:
            raise RuntimeError("Backpressure fixture Millstone is not powered.")
        blocked = mill_inventory(world)
        if blocked != (1, 64):
            raise RuntimeError(f"Could not load the blocked fixture inventory: {blocked}")
        for _ in range(5):
            world.step_to(world.clock() + 1)
        blocked_timer = scalar(world, "Timer")
        for _ in range(5):
            world.step_to(world.clock() + 1)
        still_blocked = mill_inventory(world)
        if still_blocked != blocked or scalar(world, "Timer") != blocked_timer:
            raise RuntimeError(
                "Full Millstone output did not pause processing without consuming input: "
                f"inventory {blocked} -> {still_blocked}, timer {blocked_timer} -> {scalar(world, 'Timer')}"
            )

        # Java checks for any full output slot before ticking its processing timer.
        # Java checks for any full output slot before ticking its processing timer.
        # Wheat has one guaranteed flour result plus up to two chance outputs.
        world.command(f"/item replace block {MILL} container.{OUTPUT_SLOT} with create:wheat_flour 63")
        if mill_inventory(world) != (1, 63):
            raise RuntimeError(f"Freeing one output item changed the wrong inventory: {mill_inventory(world)}")
        try:
            wait_for(world, lambda: mill_inventory(world)[0] == 0 and mill_inventory(world)[1] >= 64,
                     "the Millstone to resume and finish wheat processing")
        except RuntimeError as error:
            raise RuntimeError(
                f"{error} Final inventory={mill_inventory(world)}, "
                f"timer={scalar(world, 'Timer')}, speed={scalar(world, 'Speed')}, "
                f"Millstone={block(world, MILL)}"
            ) from error
        final = mill_inventory(world)
        if final[0] != 0 or not 64 <= final[1] <= 66:
            raise RuntimeError(f"Millstone output was lost or duplicated after backpressure: {final}")

    print("Full output paused Millstone processing; freeing one slot resumed wheat processing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
