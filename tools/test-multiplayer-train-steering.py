#!/usr/bin/env python3
"""Drive a real train from the guest client through a Java-tested junction."""

import argparse
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

curved = import_module("test-curved-train")
multiplayer = import_module("test-multiplayer")
train = curved.train
curved.Z = train.Z = 72
X, Y, Z = curved.X, curved.Y, curved.Z
train.STATION = (X, Y, Z + 2)
GUEST = "TrainGuest"


def take_controls(host, guest, *, origin=(X, Y, Z)):
    x, y, z = origin
    at = (x + 0.5, y, z - 1.3)
    host.commands((
        f"/tp @s {x + 7.5} {y + 2} {z - 4.5}",
        f"/gamemode survival {GUEST}",
        f"/clear {GUEST}",
        f"/attribute {GUEST} minecraft:movement_speed base set 0",
        f"/attribute {GUEST} minecraft:gravity base set 0",
        f"/tp {GUEST} {' '.join(map(str, at))}",
    ))
    multiplayer.until("the guest to reach the controls", lambda: (
        all(isclose(a, b, abs_tol=1e-5) for a, b in zip(guest.call("state")["player"]["position"], at, strict=True))
    ))
    guest.call("look-at", x + 1.5, y + 3.45, z + 0.5)
    guest.call("mouse", "right", "click")
    uuid = host.command(f"/data get entity {GUEST} UUID").partition("data: ")[2]
    if not uuid.startswith("[I;"):
        raise RuntimeError(f"Unexpected guest UUID data: {uuid}")
    command = f"/data get entity {train.ENTITY} CreateTrain.Driver"
    try:
        multiplayer.until("the guest to claim the authoritative controls", lambda: (
            host.command(command).endswith(uuid)
        ))
    except RuntimeError as error:
        raise RuntimeError(f"{error}. Guest UUID {uuid}, train Driver: {host.command(command)}") from error


def run(args):
    with (ROOT / "fixtures/train_steer_right-java.csv").open() as source:
        rows = [row for row in csv.DictReader(source) if int(row["tick"]) <= 96]
    with fixture_world(args, "Train-guest-steering", train.STRUCTURE, render=True, pack=args.pack) as host:
        train.setup(host, lambda control: curved.layout(control, branching=True), take_controls=False)
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-steer-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
            scenario="train-guest-steering", pack=args.pack,
        ) as guest:
            multiplayer.until("the train guest to join", lambda: any(
                item["name"] == GUEST and item["placed"] for item in host.call("lan", "status")["guests"]
            ))
            take_controls(host, guest)
            start = host.clock()
            first = int(rows[0]["tick"])
            for row in rows:
                tick = int(row["tick"])
                if tick != first:
                    host.step_to(start + tick - first)
                actual = curved.sample(host)
                for key, value in zip(curved.KEYS, actual, strict=True):
                    if not isclose(value, float(row[key]), rel_tol=0.0, abs_tol=7e-6):
                        raise RuntimeError(f"Tick {tick}: guest-driven {key} was {value}, Java {row[key]}.")
                if tick == 24:
                    guest.call("key", "w", "down")
                    guest.call("key", "d", "down")
                    guest.call("wait", 4)
                if 32 <= tick and tick % 3 == 2:
                    x = X + (actual[1] + actual[4]) / 2
                    z = Z + (actual[3] + actual[6]) / 2
                    host.command(f"/tp {GUEST} {x:.6f} {Y + 4} {z + 1.5:.6f}")
                    guest.call("wait", 3)
            guest.call("key", "w", "up")
            guest.call("key", "d", "up")
    print(f"A real guest drove through the right turn. The host matched Java wheel positions and speed on all {len(rows)} ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
