#!/usr/bin/env python3
"""Compare the original Players Seated condition editor and saved component."""

import argparse
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

entry = import_module("test-train-schedule-entry")
delay = import_module("test-train-schedule-delay")
multiplayer = delay.multiplayer
GUEST = "SeatCountEditor"


def save(world, actor, who, expected):
    actor.call("click-button", "Confirm Condition")
    actor.call("click-button", "Done")
    actor.call("wait", 8)
    delay.check_saved(world, actor, who, expected)


def scroll_players(actor, direction, count, *, shift=False):
    if shift:
        actor.call("key", "shift", "down")
    try:
        delay.scroll(actor, "Players", direction, count)
    finally:
        if shift:
            actor.call("key", "shift", "up")


def exercise(world, actor, who, expected):
    delay.prepare_item(world, actor, who)
    entry.use(actor)
    actor.call("click-button", "Add Action")
    actor.call("click-button", "Station Name")
    actor.call("type", "Waiting Station")
    actor.call("click-button", "Confirm Action")
    actor.call("click-button", "Wait: 5s")
    delay.scroll(actor, "Continue if/after:", -1, 5)
    save(world, actor, who, expected["default"])

    entry.use(actor)
    actor.call("click-button", "0 Players")
    scroll_players(actor, 1, 1)
    delay.scroll(actor, "Conditional", -1)
    scroll_players(actor, 1, 1, shift=True)
    save(world, actor, who, expected["shift"])

    entry.use(actor)
    actor.call("click-button", "5 Players")
    scroll_players(actor, 1, 5, shift=True)
    save(world, actor, who, expected["upper"])

    entry.use(actor)
    actor.call("click-button", "20 Players")
    scroll_players(actor, -1, 5, shift=True)
    delay.scroll(actor, "Conditional", 1)
    save(world, actor, who, expected["lower"])

    entry.use(actor)
    assert entry.buttons(actor)["0 Players"]["enabled"]
    actor.call("click-button", "Done")


def run(args):
    fixture = ROOT / "fixtures/train-schedule-passenger-count-editor-java.json"
    expected = json.loads(fixture.read_text())
    scenario = "train-schedule-passenger-count-editor-lan" if args.multiplayer else "train-schedule-passenger-count-editor"
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
        with TemporaryDirectory(prefix="hc-pass-ed-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST,
            render=True, scenario=scenario, pack=args.pack,
        ) as guest:
            multiplayer.until("the guest Players Seated editor to join", lambda: any(
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
    print("Players Seated matched Java's default, shifted snap, conditional selection, and clamped boundaries.")
