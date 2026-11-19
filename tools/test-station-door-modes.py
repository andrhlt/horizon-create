#!/usr/bin/env python3
"""Exercise every station door selector option through the player screen."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import fixture_world

station = import_module("test-track-station-name")
mp = station.multiplayer
X, Y, Z = station.X, station.Y, station.Z
MODES = ("NORTH", "EAST", "SOUTH", "WEST", "NONE", "ALL")


def mode(world):
    return world.command(f"/data get block {X} {Y} {Z} DoorControl")


def select(world, actor):
    for expected in MODES:
        station.open_station(actor)
        control = next(b for b in actor.call("screen")["buttons"] if b["label"] == "Onboard Door Control")
        direction = 1 if expected == "ALL" else -1
        count = 5 if expected == "ALL" else 1
        for _ in range(count):
            actor.call("scroll-at", control["x"] + control["w"] / 2, control["y"] + control["h"] / 2, direction)
        actor.call("key", "esc", "tap")
        actor.call("wait", 5)
        mp.until(f"{expected} door control", lambda: f'"{expected}"' in mode(world))


def run(args):
    with fixture_world(args, "station-door-modes", station.train.STRUCTURE, render=True,
                       pack=args.pack, env={"HORIZON_NO_AUDIO": "1"}) as world:
        station.place(world)
        if args.multiplayer:
            port = world.call("lan", "open", "0", "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-station-door-modes-") as scratch, mp.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", station.GUEST,
                render=True, scenario="station-door-modes", pack=args.pack,
                env={"HORIZON_NO_AUDIO": "1"},
            ) as guest:
                mp.until("guest to join", lambda: any(e["name"] == station.GUEST and e["placed"]
                                                       for e in world.call("lan", "status")["guests"]))
                world.command(f"/gamemode survival {station.GUEST}")
                world.command(f"/tp @s {X + 2.5} {Y} {Z + 2.5}")
                world.command(f"/tp {station.GUEST} {X + .5} {Y} {Z + 2.5} 180 20")
                guest.call("wait", 5)
                select(world, guest)
        else:
            select(world, world)
            world.restart()
            if '"ALL"' not in mode(world):
                raise RuntimeError("Station door mode did not survive a world reload")
    print("All six station door modes reached the host through the player screen.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
