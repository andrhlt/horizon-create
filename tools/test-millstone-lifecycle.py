#!/usr/bin/env python3
"""Check idle Millstone contents and partway processing across world reopen."""

import argparse
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/wheat_milling.nbt")
BARREL = "5 102 -11"
MILL = "5 98 -11"
HOPPER = "5 97 -11"
CHEST = "4 97 -11"
LEVER = "4 102 -11"
MOTOR_AREA = (range(3, 7), range(96, 103), range(-12, -9))


def block(world, pos):
    return world.command(f"/data get block {pos}")


def timer(world):
    match = re.search(r"\bTimer: (-?\d+)", block(world, MILL))
    if not match:
        raise RuntimeError("Millstone NBT did not expose its processing timer.")
    return int(match[1])


def scalar(world, key):
    match = re.search(rf"\b{re.escape(key)}: (-?\d+(?:\.\d+)?)", block(world, MILL))
    if not match:
        raise RuntimeError(f"Millstone NBT did not expose {key}.")
    return float(match[1])


def motor_position(world):
    for x in MOTOR_AREA[0]:
        for y in MOTOR_AREA[1]:
            for z in MOTOR_AREA[2]:
                if world.call("block", x, y, z)["block"] == "create:creative_motor":
                    return x, y, z
    raise RuntimeError("Wheat fixture creative motor was not found.")


def count_item(tag, item, slots=None):
    total = 0
    for stack in re.findall(r"\{([^{}]*\bid: \"[a-z0-9_.-]+:[^{}]+)\}", tag):
        found = re.search(r'\bid: "[a-z0-9_.-]+:([^" ]+)"', stack)
        slot = re.search(r"\bSlot: (\d+)", stack)
        if not found or found[1] != item or (slots and (not slot or not slots(int(slot[1])))):
            continue
        count = re.search(r"\b(?:count|Count): (\d+)", stack)
        total += int(count[1]) if count else 1
    return total


def item_totals(world):
    values = [block(world, pos) for pos in (BARREL, MILL, HOPPER, CHEST)]
    wheat = sum(count_item(value, "wheat") for value in values)
    flour = sum(count_item(value, "wheat_flour") for value in values)
    seeds = sum(count_item(value, "wheat_seeds") for value in values)
    return wheat, flour, seeds


def setup(world, powered):
    world.command("/place template create:gametest/processing/wheat_milling 3 96 -12")
    world.command(f"/setblock {LEVER} minecraft:lever[face=wall,facing=west,powered={'true' if powered else 'false'}]")
    world.commands((
        f"/item replace block {BARREL} container.13 with minecraft:air",
        f"/item replace block {BARREL} container.0 with minecraft:air",
        f"/item replace block {MILL} container.0 with minecraft:wheat 1",
    ))


def wait_for(world, predicate, description, ticks=80):
    for _ in range(ticks):
        if predicate():
            return
        world.step_to(world.clock() + 1)
    raise RuntimeError(f"Timed out waiting for {description}.")


def idle_reopen(args):
    with fixture_world(args, "MillstoneIdleReopen", STRUCTURE, env={
        "CREATE_WHEAT_TRACE_ORIGIN": "3,96,-12",
        "CREATE_WHEAT_TRACE_SEED": "2",
    }, pack=args.pack) as world:
        setup(world, powered=True)
        wait_for(world, lambda: timer(world) > 0,
                 "the powered Millstone to start its wheat cycle")
        motor = " ".join(map(str, motor_position(world)))
        world.command(f"/data modify block {motor} ScrollValue set value 0")
        wait_for(world, lambda: scalar(world, "Speed") == 0,
                 "the Millstone network to stop after its motor is set to zero")
        before = (timer(world), item_totals(world))
        if before[1] != (1, 0, 0):
            raise RuntimeError(f"Unexpected stopped Millstone inventory before reopen: {before}")
        for _ in range(2):
            world.step_to(world.clock() + 1)
        if timer(world) != before[0]:
            raise RuntimeError(f"Millstone timer advanced without power: {before[0]} -> {timer(world)}")
        world.restart()
        after = (timer(world), item_totals(world))
        if after != before:
            raise RuntimeError(f"Idle Millstone state changed after reopen: {before} -> {after}")


def active_reopen(args):
    with fixture_world(args, "MillstoneActiveReopen", STRUCTURE, env={
        "CREATE_WHEAT_TRACE_ORIGIN": "3,96,-12",
        "CREATE_WHEAT_TRACE_SEED": "2",
    }, pack=args.pack) as world:
        setup(world, powered=True)
        wait_for(world, lambda: 1 <= timer(world) < 100,
                 "the Millstone to reach partway through its wheat cycle")
        before = item_totals(world)
        if before != (1, 0, 0):
            raise RuntimeError(f"Wheat was lost or processed before the partway save: {before}")
        world.restart()
        try:
            wait_for(world, lambda: (items := item_totals(world))[0] == 0 and items[1] >= 1,
                     "the saved wheat cycle to resume and produce flour", ticks=80)
        except RuntimeError as error:
            raise RuntimeError(
                f"{error} Final timer={timer(world)}, speed={scalar(world, 'Speed')}, "
                f"items={item_totals(world)}, Millstone={block(world, MILL)}"
            ) from error
        final = item_totals(world)
        if final[0] != 0 or not 1 <= final[1] <= 3 or final[2] not in (0, 1):
            raise RuntimeError(f"Millstone did not conserve its wheat within recipe output bounds: {final}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    idle_reopen(args)
    active_reopen(args)
    print("Stopped Millstone input and partway wheat processing survived world reopen.")


if __name__ == "__main__":
    main()
