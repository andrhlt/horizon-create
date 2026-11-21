#!/usr/bin/env python3
"""Check equipped Cardboard armor and disguise survive a cold world reopen."""
import argparse
import csv
from pathlib import Path

from fixture_world import fixture_world
from importlib import import_module

mp = import_module("test-multiplayer")

SLOTS = ("head", "chest", "legs", "feet")


def worn(actor):
    armor = {slot["part"]: slot.get("item") for slot in actor.call("inventory")["armor"]}
    return tuple(armor.get(part) for part in ("head", "chest", "legs", "feet"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()

    with (Path(__file__).resolve().parents[1] / "fixtures/cardboard-armor-java.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    items = [row["name"] for row in rows]
    expected = tuple(row["name"] for row in rows)
    with fixture_world(args, "CardboardArmorReopen", render=False, pack=args.pack) as world:
        world.commands(tuple(
            f"/item replace entity @s armor.{slot} with {item}"
            for slot, item in zip(SLOTS, expected, strict=True)
        ))
        mp.until("the complete Cardboard set to equip", lambda: worn(world) == expected)
        world.call("key", "shift", "down")
        active = world.call("state")["player"]
        if not active["cardboard_disguised"] or (round(active["body_width"], 4), round(active["body_height"], 4)) != (0.6, 0.8):
            raise AssertionError(f"Full set did not activate the crouching disguise before save: {active}")

        world.restart()
        mp.until("the reopened Cardboard set to appear equipped", lambda: worn(world) == expected)
        world.call("key", "shift", "down")
        reopened = world.call("state")["player"]
        if not reopened["cardboard_disguised"] or (round(reopened["body_width"], 4), round(reopened["body_height"], 4)) != (0.6, 0.8):
            raise AssertionError(f"Reopened full set failed to activate disguise: {reopened}")
        if reopened["visibility"] != 0:
            raise AssertionError(f"Reopened disguise did not suppress mob visibility: {reopened['visibility']}")

    print("Full Cardboard equipment survived cold reopen and reactivated crouching disguise with zero mob visibility.")


if __name__ == "__main__":
    main()
