#!/usr/bin/env python3
"""Compare the original item and fluid cargo threshold editors and ghost samples."""

import argparse
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

entry = import_module("test-train-schedule-entry")
delay = import_module("test-train-schedule-delay")
multiplayer = delay.multiplayer
GUEST = "CargoCompare"
STOCK = {"minecraft:paper": 7, "minecraft:water_bucket": 1}


def quick_move(actor, inventory_slot=None):
    bounds = entry.buttons(actor)["Reference Item"]
    if inventory_slot is None:
        x, y = bounds["x"] + 8, bounds["y"] + 8
    else:
        left, top = bounds["x"] - 54, bounds["y"] - 88
        x, y = left + 54 + inventory_slot * 18, top + 206
    actor.call("key", "shift", "down")
    try:
        actor.call("click-at", int(x), int(y))
    finally:
        actor.call("key", "shift", "up")


def amount(actor, text):
    actor.call("click-button", "Threshold")
    actor.call("key", "ctrl", "down")
    actor.call("key", "a", "tap")
    actor.call("key", "ctrl", "up")
    actor.call("type", text)


def confirm(world, actor, who, expected):
    actor.call("click-button", "Confirm Condition")
    actor.call("click-button", "Done")
    actor.call("wait", 8)
    delay.check_saved(world, actor, who, expected)
    counts = actor.call("inventory")["counts"]
    if any(counts.get(item) != count for item, count in STOCK.items()):
        raise RuntimeError(f"Ghost references changed the inventory: {counts}")


def exercise(world, actor, who, expected):
    delay.prepare_item(world, actor, who)
    world.commands(tuple(
        f"/item replace entity {who} hotbar.{index} with {item} {count}"
        for index, (item, count) in enumerate(STOCK.items(), start=1)
    ))
    multiplayer.until("the cargo samples", lambda: all(
        actor.call("inventory")["counts"].get(item) == count for item, count in STOCK.items()
    ))
    entry.use(actor)
    actor.call("click-button", "Add Action")
    actor.call("click-button", "Station Name")
    actor.call("type", "Waiting Station")
    actor.call("click-button", "Confirm Action")
    actor.call("click-button", "Wait: 5s")
    delay.scroll(actor, "Continue if/after:", -1, 3)

    quick_move(actor, 1)
    delay.scroll(actor, "Comparison", -1, 2)
    delay.scroll(actor, "Item Measure", -1)
    amount(actor, "32")
    confirm(world, actor, who, expected["items"])

    entry.use(actor)
    actor.call("click-button", "= 32▤")
    delay.scroll(actor, "Continue if/after:", 1)
    quick_move(actor)
    quick_move(actor, 2)
    delay.scroll(actor, "Comparison", -1)
    amount(actor, "12")
    confirm(world, actor, who, expected["fluid"])

    entry.use(actor)
    actor.call("click-button", "< 12b")
    widgets = entry.buttons(actor)
    assert {"Reference Item", "Comparison", "Threshold"}.issubset(widgets)
    assert "Item Measure" not in widgets
    confirm(world, actor, who, expected["fluid"])


def run(args):
    fixture = ROOT / "fixtures" / "train-schedule-cargo-comparison-java.json"
    expected = json.loads(fixture.read_text())
    scenario = "train-schedule-cargo-comparison-lan" if args.multiplayer else "train-schedule-cargo-comparison"
    with fixture_world(args, scenario, render=True, pack=args.pack) as world:
        world.commands((
            "/fill 4 95 36 15 95 46 minecraft:smooth_stone",
            "/tp @s 8.5 96 41.3 -90 -25",
            "/gamemode survival",
        ))
        if not args.multiplayer:
            exercise(world, world, "@s", expected)
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-cargo-ed-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST,
            render=True, scenario=scenario, pack=args.pack,
        ) as guest:
            multiplayer.until("the cargo editor guest to join", lambda: any(
                player["name"] == GUEST and player["placed"] for player in world.call("lan", "status")["guests"]
            ))
            world.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} 10.5 96 41.3 -90 -25"))
            guest.call("wait", 4)
            exercise(world, guest, GUEST, expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
    print("Item and fluid cargo threshold controls reopened and retained Java's exact operators, units, amounts, and ghost samples.")
