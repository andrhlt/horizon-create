#!/usr/bin/env python3
"""Compare the actual Weighted Ejector lid draw transform with Java Create."""
import argparse
import csv
import json
import os
from contextlib import ExitStack
from importlib import import_module
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
DIRECTIONS = {(0, -1): "north", (0, 1): "south", (-1, 0): "west", (1, 0): "east"}
POSITIONS = {name: (5 + i * 2, 104, -11) for i, name in enumerate(DIRECTIONS.values())}
LIFTS = (0, .25, .50, .75, 1)
TRACE = "CREATE_EJECTOR_LID_HORIZON "


def position(name):
    return " ".join(map(str, POSITIONS[name]))


def reference(path):
    with path.open() as source:
        return {(row[0], float(row[1])): tuple(map(float, row[2:]))
                for row in list(csv.reader(source))[1:]}


def setup(control):
    control.commands((
        "/fill 3 103 -14 13 103 -4 minecraft:smooth_stone",
        "/fill 3 104 -14 13 111 -4 minecraft:air",
        *(f'/setblock {position(name)} create:weighted_ejector[facing={name}]{{State:"CHARGED"}}'
          for name in POSITIONS),
        "/gamemode spectator @s",
        "/tp @s 8.5 107.8 -4.5",
    ))
    control.call("look-at", 8.5, 104.5, -10.5)


def rendered(log, clock, lift):
    seen = {}
    deadline = monotonic() + 5
    while seen.keys() != POSITIONS.keys() and monotonic() < deadline:
        for line in reversed(log.read_text().splitlines()):
            if not line.startswith(TRACE):
                continue
            try:
                tick, x, z, progress, vertices, encoded = line[len(TRACE):].split(",", 5)
                if (clock is not None and int(tick) != clock) or not isclose(float(progress), lift, abs_tol=.000001):
                    continue
                name = DIRECTIONS[int(x), int(z)]
                points = tuple(value for point in json.loads(encoded) for value in point)
                if name not in seen and int(vertices) > 0 and len(points) == 12:
                    seen[name] = points
            except (ValueError, KeyError, TypeError):
                continue  # the client and server can write to the same log concurrently
        if seen.keys() != POSITIONS.keys():
            sleep(.07)
    if seen.keys() != POSITIONS.keys():
        raise RuntimeError(f"Missing rendered Ejector top for {POSITIONS.keys() - seen.keys()} at progress {lift}.")
    return seen


def verify(args):
    samples = reference(args.reference)
    differences = []
    os.environ["CREATE_EJECTOR_LID_RENDER"] = "1"
    with ExitStack() as stack:
        world = "EjectorLidRenderLAN" if args.multiplayer else "EjectorLidRender"
        host = stack.enter_context(fixture_world(args, world, render=True, pack=args.pack))
        setup(host)
        peers = {"host": host}
        if args.multiplayer:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejector-lid-")))
            name = "EjectLidGuest"
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, render=True, scenario="ejector-lid", pack=args.pack,
            ))
            multiplayer.until("the Ejector render guest joins", lambda: any(
                player["name"] == name and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((f"/gamemode spectator {name}", f"/tp {name} 8.5 107.8 -4.5"))
            multiplayer.until("guest sees the Ejectors", lambda:
                              guest.call("block", *POSITIONS["north"])["block"] == "create:weighted_ejector")
            guest.call("look-at", 8.5, 104.5, -10.5)
            peers["guest"] = guest
        for lift in LIFTS:
            host.commands(f'/data merge block {position(name)} '
                          f'{{Lid:{{Value:{lift:.2f}f,Previous:{lift:.2f}f}}}}'
                          for name in POSITIONS)
            tick = host.clock() + 1
            host.step_to(tick)
            for role, peer in peers.items():
                log = peer.socket.parent / "ctl.log"
                for name, got in rendered(log, tick if role == "host" else None, lift).items():
                    want = samples[name, lift]
                    error = max(abs(a - b) for a, b in zip(got, want, strict=True))
                    if error > .000003:
                        differences.append((role, name, lift, error))
    if differences:
        raise RuntimeError(f"The Ejector lid differed from Java on {len(differences)} render samples: {differences[:8]}")
    print(f"Original Ejector lid pose and model matched all {len(peers) * len(POSITIONS) * len(LIFTS)} Java render samples.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/depot-ejector-lid-java.csv")
    verify(parser.parse_args())
