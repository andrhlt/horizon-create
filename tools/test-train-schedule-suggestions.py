#!/usr/bin/env python3
"""Replay Java's station name suggestions through the real Schedule editor."""

import argparse
import json
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

entry = import_module("test-train-schedule-entry")
delay = import_module("test-train-schedule-delay")
multiplayer = delay.multiplayer
GUEST = "StationSearch"
X, Y, Z = 9, 112, -8


def layout(world):
    world.commands((
        f"/fill {X-4} {Y-1} {Z-6} {X+21} {Y-1} {Z+17} minecraft:smooth_stone",
        f"/fill {X-3} {Y} {Z} {X+19} {Y} {Z} create:track[shape=xo]",
        f"/fill {X+12} {Y} {Z+12} {X+19} {Y} {Z+12} create:track[shape=xo]",
        "/gamemode survival",
    ))
    for offset, row, name in (
        (3, 0, "Harbor"), (6, 0, "Harbor"), (10, 0, "Harbor West"), (16, 12, "East Yard"),
    ):
        x, z = X + offset, Z + row
        world.commands((
            "/item replace entity @s hotbar.0 with create:track_station",
            f"/tp @s {x+2.5} {Y} {z + .5} 90 20",
        ))
        world.call("key", "1", "tap")
        world.call("wait", 3)
        world.call("look-at", x + .5, Y + .06, z + .5)
        world.call("mouse", "right", "click")
        world.call("wait", 3)
        world.command(f"/tp @s {x+.5} {Y} {z+4.5} 180 20")
        world.call("wait", 3)
        world.call("interact", x, Y-1, z+2, "up")
        world.step_to(world.clock() + 1)
        block = world.call("block", x, Y, z+2)
        if block["block"] != "create:track_station":
            raise RuntimeError(f"Survival Track Station did not bind at {(x, Y, z+2)}: {block}")
        world.command(f"/data merge block {x} {Y} {z+2} {{Name:{json.dumps(name)}}}")


def check_options(actor, expected, names):
    actual = [label for label in entry.buttons(actor) if label in names]
    if actual != expected:
        raise RuntimeError(f"Java suggests {expected}, Horizon suggests {actual}")


def exercise(world, actor, who, expected):
    world.command(f"/tp {who} {X+.5} {Y} {Z-4.5} 180 20")
    delay.prepare_item(world, actor, who)
    names = set(expected["blank"])
    entry.use(actor)
    actor.call("click-button", "Add Action")
    actor.call("click-button", "Station Name")
    check_options(actor, expected["blank"], names)
    actor.call("type", "h")
    check_options(actor, expected["prefix"], names)
    actor.call("key", "tab", "tap")
    actor.call("click-button", "Confirm Action")
    actor.call("click-button", "Done")
    actor.call("wait", 8)
    delay.check_saved(world, actor, who, expected["selected"])

    entry.use(actor)
    actor.call("click-button", "Add Action")
    actor.call("click-button", "Station Name")
    check_options(actor, expected["restricted"], names)
    actor.call("click-button", "Cancel Action")
    actor.call("click-button", "Harbor")
    actor.call("click-button", "Station Name")
    actor.call("key", "ctrl", "down")
    actor.call("key", "a", "tap")
    actor.call("key", "ctrl", "up")
    actor.call("type", "Missing")
    actor.call("click-button", "Confirm Action")
    actor.call("click-button", "Add Action")
    actor.call("click-button", "Station Name")
    check_options(actor, expected["fallback"], names)
    actor.call("click-button", "Cancel Action")
    actor.call("click-button", "Done")
    actor.call("wait", 8)


def run(args):
    expected = json.loads((ROOT / "fixtures/train-schedule-suggestions-java.json").read_text())
    scenario = "train-schedule-suggestions-lan" if args.multiplayer else "train-schedule-suggestions"
    with fixture_world(args, scenario, render=True, pack=args.pack) as world:
        layout(world)
        if not args.multiplayer:
            exercise(world, world, "@s", expected)
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-sched-sug-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST,
            render=True, scenario=scenario, pack=args.pack,
        ) as guest:
            multiplayer.until("the Schedule editor guest", lambda: any(
                link["name"] == GUEST and link["placed"] for link in world.call("lan", "status")["guests"]
            ))
            world.command(f"/gamemode survival {GUEST}")
            exercise(world, guest, GUEST, expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
    print("The suggestions match Java's order, prefix, deduplication, Tab selection, linked graph restriction, and fallback.")
