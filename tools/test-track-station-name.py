#!/usr/bin/env python3
"""Rename a bound Track Station with the actual host and LAN guest editors."""

import argparse
import csv
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

train = import_module("test-simple-train")
multiplayer = import_module("test-multiplayer")
X, Y, Z = train.STATION
GUEST = "StationNamer"


def place(world):
    world.commands((
        f"/fill {X - 4} {Y-1} {Z-4} {X+4} {Y-1} {Z+4} minecraft:smooth_stone",
        f"/fill {X-3} {Y} {Z-2} {X+3} {Y} {Z-2} create:track[shape=xo]",
        "/gamemode survival",
        "/item replace entity @s hotbar.0 with create:track_station",
        f"/tp @s {X+2.5} {Y} {Z-1.5} 90 20",
    ))
    world.call("wait", 3)
    world.call("key", "1", "tap")
    train.click_track(world, X)
    world.command(f"/tp @s {X + .5} {Y} {Z + 2.5} 180 20")
    world.call("wait", 3)
    world.call("interact", X, Y - 1, Z, "up")
    world.step_to(world.clock()+1)
    if world.call("block", X, Y, Z)["block"] != "create:track_station":
        raise RuntimeError("The survival Track Station did not place.")


def name(world):
    output = world.command(f"/data get block {X} {Y} {Z} Name")
    if "block data: " not in output:
        return None
    literal = output.split("block data: ", 1)[1]
    try:
        return json.loads(literal)
    except ValueError:
        return literal


def open_station(actor):
    multiplayer.until("the station to load on the client",
                      lambda: actor.call("block", X, Y, Z)["block"] == "create:track_station")
    actor.call("look-at", X + .5, Y + .45, Z + .5)
    actor.call("mouse", "right", "click")
    multiplayer.until("the station screen's name field", lambda: any(
        button["label"] == "Station Name" and button["enabled"]
        for button in actor.call("screen")["buttons"]
    ))


def edit(actor, value, *, close=False):
    actor.call("click-button", "Station Name")
    actor.call("type", value)
    actor.call("key", "esc" if close else "enter", "tap")
    actor.call("wait", 5)


def exercise(world, actor, cases):
    open_station(actor)
    edit(actor, "Main Platform")
    multiplayer.until("Enter to set the station name", lambda: name(world) == cases["first"])
    edit(actor, "    ")
    if name(world) != cases["blank"]:
        raise RuntimeError("A blank name changed the authoritative station label.")
    edit(actor, "  Gare du Nord ★  ", close=True)
    multiplayer.until("closing the editor to preserve spaces and Unicode", lambda: name(world) == cases["unicode"])
    open_station(actor)
    edit(actor, "1234567890123456789012345overflow", close=True)
    multiplayer.until("the 25-unit station name to persist", lambda: name(world) == cases["boundary"])


def run(args):
    with (ROOT / "fixtures/track-station-name-java.csv").open() as source:
        cases = {row["action"]: row["live_name"] for row in csv.DictReader(source)}
    scenario = "Track-station-name-LAN" if args.multiplayer else "Track-station-name"
    with fixture_world(args, scenario, train.STRUCTURE, render=True, pack=args.pack) as world:
        place(world)
        if args.multiplayer:
            port = world.call("lan", "open", "0", "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-station-name-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST,
                render=True, scenario=scenario, pack=args.pack,
            ) as guest:
                multiplayer.until("the guest to join", lambda: any(
                    entry["name"] == GUEST and entry["placed"] for entry in world.call("lan", "status")["guests"]
                ))
                world.command(f"/gamemode survival {GUEST}")
                world.command(f"/tp @s {X + 2.5} {Y} {Z + 2.5}")
                world.command(f"/tp {GUEST} {X + .5} {Y} {Z + 2.5} 180 20")
                guest.call("wait", 5)
                exercise(world, guest, cases)
        else:
            exercise(world, world, cases)
            world.restart()
            if name(world) != cases["boundary"]:
                raise RuntimeError("The saved Track Station name did not survive world reload.")
    print("Real Track Station rename, blank rejection, Unicode and 25-character input matched Java.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
