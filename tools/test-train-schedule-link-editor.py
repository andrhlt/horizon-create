#!/usr/bin/env python3
"""Compare Java's Redstone Link Schedule ghost filters and saved components."""

import argparse
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

entry = import_module("test-train-schedule-entry")
delay = import_module("test-train-schedule-delay")
multiplayer = delay.multiplayer
GUEST = "LinkEditor"
SAMPLES = {"minecraft:paper": 7, "minecraft:redstone": 4}


def save(world, actor, who, wanted):
    actor.call("click-button", "Confirm Condition")
    actor.call("click-button", "Done")
    actor.call("wait", 8)
    delay.check_saved(world, actor, who, wanted)
    counts = actor.call("inventory")["counts"]
    if any(counts.get(item) != count for item, count in SAMPLES.items()):
        raise RuntimeError(f"Ghost samples changed the carried source stacks: {counts}")


def quick_move(actor, hotbar_index=None):
    bounds = entry.buttons(actor)["Frequency #1"]
    if hotbar_index is None:
        x, y = bounds["x"] + 8, bounds["y"] + 8
    else:
        left, top = bounds["x"] - 54, bounds["y"] - 88
        x, y = left + 54 + hotbar_index * 18, top + 206
    actor.call("key", "shift", "down")
    try:
        actor.call("click-at", int(x), int(y))
    finally:
        actor.call("key", "shift", "up")


def exercise(world, actor, who, expected):
    delay.prepare_item(world, actor, who)
    world.commands(tuple(
        f"/item replace entity {who} hotbar.{index} with {item} {count}"
        for index, (item, count) in enumerate(SAMPLES.items(), start=1)
    ))
    multiplayer.until("the frequency sample stacks", lambda: all(
        actor.call("inventory")["counts"].get(item) == count for item, count in SAMPLES.items()
    ))
    entry.use(actor)
    actor.call("click-button", "Add Action")
    actor.call("click-button", "Station Name")
    actor.call("type", "Waiting Station")
    actor.call("click-button", "Confirm Action")
    actor.call("click-button", "Wait: 5s")
    delay.scroll(actor, "Continue if/after:", -1, 4)
    save(world, actor, who, expected["default"])

    entry.use(actor)
    actor.call("click-button", "Link On")
    quick_move(actor, 1)
    quick_move(actor, 2)
    delay.scroll(actor, "Frequency state:", -1)
    save(world, actor, who, expected["inverted"])

    entry.use(actor)
    actor.call("click-button", "Link Off")
    quick_move(actor)
    delay.scroll(actor, "Frequency state:", 1)
    save(world, actor, who, expected["cleared"])

    entry.use(actor)
    assert entry.buttons(actor)["Link On"]["enabled"]
    actor.call("click-button", "Done")


def run(args):
    expected = json.loads((ROOT/"fixtures/train-schedule-link-editor-java.json").read_text())
    scenario = "train-schedule-link-editor-lan" if args.multiplayer else "train-schedule-link-editor"
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
        with TemporaryDirectory(prefix="hc-link-ed-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST,
            render=True, scenario=scenario, pack=args.pack,
        ) as guest:
            multiplayer.until("the Redstone Link guest editor to join", lambda: any(
                link["name"] == GUEST and link["placed"] for link in world.call("lan", "status")["guests"]
            ))
            world.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} 10.5 96 41.3 -90 -25"))
            guest.call("wait", 5)
            exercise(world, guest, GUEST, expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
    print("Redstone Link matched Java's ghost quick moves, copied frequencies, clearing, and inversion.")
