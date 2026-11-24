#!/usr/bin/env python3
"""Craft, place, and reopen a Weighted Ejector during hold and flight."""

import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

crafting = import_module("test-survival-crafting")
placement = import_module("test-ejector-target-placement")
launch = import_module("test-depot-ejector-launch")
threshold = import_module("test-depot-ejector-threshold")
obstacle = import_module("test-depot-ejector-obstacle")
lifecycle = import_module("test-press-lifecycle")
multiplayer = import_module("test-multiplayer")
track = import_module("test-track-crafting")

EJECTOR = (5, 105, -11)
DEPOT = (9, 105, -11)
TABLE = (7, 105, -9)
POWER = (4, 105, -11)
INGREDIENTS = ("create:golden_sheet", "create:depot", "create:cogwheel")
ITEM = launch.ITEM


def craft_and_place(control):
    control.commands((
        "/fill 3 104 -14 11 104 -8 minecraft:smooth_stone",
        "/fill 3 105 -14 11 112 -8 minecraft:air",
        "/tp @s 7.5 105 -10.5",
        "/gamemode survival @s",
        f"/setblock {placement.pos_text(TABLE)} minecraft:crafting_table",
        f"/setblock {launch.DEPOT} create:depot",
        *(f"/item replace entity @s hotbar.{slot} with {item}"
          for slot, item in enumerate(INGREDIENTS)),
        f"/item replace entity @s hotbar.3 with {ITEM} 3",
        f"/item replace entity @s hotbar.4 with {ITEM} 3",
    ))
    control.call("interact", *TABLE, "up")
    for ingredient, slot in zip(INGREDIENTS, (100, 103, 106), strict=True):
        crafting.distribute(control, crafting.inventory_slot(control, ingredient), (slot,))
    crafting.craft(control, placement.EJECTOR, 1)
    control.call("close")
    assert all(multiplayer.count(control, item) == 0 for item in INGREDIENTS)
    control.call("select", placement.EJECTOR)
    control.call("key", "shift", "down")
    try:
        control.step_to(control.clock() + 1)
        control.call("interact", *DEPOT, "up")
    finally:
        control.call("key", "shift", "up")
    control.step_to(control.clock() + 1)
    assert control.call("block", DEPOT[0], DEPOT[1] + 1, DEPOT[2])["block"] == "minecraft:air"
    control.call("interact", EJECTOR[0], EJECTOR[1] - 1, EJECTOR[2], "up")
    multiplayer.until("the crafted Ejector is placed eastward", lambda:
                      "facing=east" in control.call("block", *EJECTOR)["state"])
    assert multiplayer.count(control, placement.EJECTOR) == 0
    control.call("select", 9)
    threshold.edit(control, control, 3)
    configuration(control)


def configuration(control):
    assert "facing=east" in control.call("block", *EJECTOR)["state"]
    horizontal, vertical, setting = control.commands((
        f"/data get block {launch.EJECTOR} HorizontalDistance",
        f"/data get block {launch.EJECTOR} VerticalDistance",
        f"/data get block {launch.EJECTOR} ScrollValue",
    ))
    actual = tuple(launch.value(field) for field in (horizontal, vertical, setting))
    assert actual == (4, 0, 3), actual


def count_stacks(reply):
    return sum(launch.count(stack) for stack in track.compounds(reply))


def cargo(control):
    held, incoming, flying, received = control.commands((
        f"/data get block {launch.EJECTOR} Items",
        f"/data get block {launch.EJECTOR} Incoming",
        f"/data get block {launch.EJECTOR} LaunchedItems",
        f"/data get block {launch.DEPOT} Items",
    ))
    loose = sum(entry["item"]["count"] for entry in obstacle.items_near(control, ITEM))
    # Source, in flight, destination, loose entities, player inventory.
    return (count_stacks(held) + count_stacks(incoming), count_stacks(flying),
            count_stacks(received), loose, multiplayer.count(control, ITEM))


def flight_age(control):
    return launch.value(control.command(f"/data get block {launch.EJECTOR} LaunchedItems[0].Time"))


def charge(control):
    lifecycle.wait_until(control, lambda:
                         "CHARGED" in control.command(f"/data get block {launch.EJECTOR} State"),
                         "the Ejector to charge", timeout=24)


def hold(control, expected):
    for _ in range(24):
        control.step_to(control.clock() + 1)
        actual = cargo(control)
        assert actual == expected, actual


def load(control):
    # Supply the next normal survival stack in the hotbar, then use the plate.
    control.call("select", ITEM)
    control.call("interact", *EJECTOR, "up")
    control.call("select", 9)


def await_delivery(control):
    for _ in range(24):
        actual = cargo(control)
        assert sum(actual) == 6 and actual[3] == 0, actual
        if actual == (0, 0, 3, 0, 3):
            return
        control.step_to(control.clock() + 1)
    raise RuntimeError(f"The Depot did not receive all three ingots: {actual}")


def run(args):
    with fixture_world(args, "WeightedEjectorLifecycle", render=True, pack=args.pack) as control:
        craft_and_place(control)
        control.commands((
            f"/setblock {launch.POWER} minecraft:redstone_block",
            "/setblock 5 105 -12 create:creative_motor[facing=south]{ScrollValue:128}",
        ))
        charge(control)
        load(control)
        hold(control, (3, 0, 0, 0, 3))
        control.restart()
        configuration(control)
        assert control.call("block", *POWER)["block"] == "minecraft:redstone_block"
        hold(control, (3, 0, 0, 0, 3))
        print("Survival crafting, target placement and stack-size editing passed. "
              "The powered Ejector held three ingots for 24 ticks on each side of idle reopen.", flush=True)

        control.command(f"/setblock {launch.POWER} minecraft:air")
        lifecycle.wait_until(control, lambda: (flight_age(control) or 0) == 6,
                             "three ingots reach flight age six", timeout=12)
        actual = cargo(control)
        assert actual == (0, 3, 0, 0, 3), actual
        control.command(f"/setblock {launch.POWER} minecraft:redstone_block")
        control.restart()
        configuration(control)
        assert control.call("block", *POWER)["block"] == "minecraft:redstone_block"
        age = flight_age(control)
        actual = cargo(control)
        if age is None:
            if actual != (0, 0, 3, 0, 3):
                state = control.commands((
                    f"/data get block {launch.EJECTOR} LaunchedItems",
                    f"/data get block {launch.EJECTOR} Items",
                    f"/data get block {launch.DEPOT} Items",
                ))
                raise RuntimeError(
                    f"The flight ended during reopen without a conserved Depot delivery: cargo={actual}, state={state}"
                )
        elif not 6 <= age < 20 or actual != (0, 3, 0, 0, 3):
            raise RuntimeError(f"Active flight changed unexpectedly during reopen: age={age}, cargo={actual}")
        await_delivery(control)
        # Load the second stack before collecting the first so the selected slot
        # always supplies exactly three, without merging the two batches.
        charge(control)
        load(control)
        hold(control, (3, 0, 3, 0, 0))
        control.call("interact", *DEPOT, "up")
        actual = cargo(control)
        assert actual == (3, 0, 0, 0, 3), actual
        control.command(f"/setblock {launch.POWER} minecraft:air")
        await_delivery(control)
        control.call("interact", *DEPOT, "up")
        actual = cargo(control)
        assert actual == (0, 0, 0, 0, 6), actual
        hold(control, (0, 0, 0, 0, 6))
    print("Re-powering during flight preserved the cargo through reopen. "
          "Removing power released the next stack, and all six ingots were retrieved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
