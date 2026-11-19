#!/usr/bin/env python3
"""Drive a real assembled train past two pairs of signals and compare occupancy."""

import argparse
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

train = import_module("test-simple-train")
signals = import_module("test-train-signal")
TARGETS = (train.X - 2, train.X + 7)
LOCATIONS = [(x, train.Y, train.Z + side) for x in TARGETS for side in (3, -3)]
KEYS = ("west_in", "west_out", "east_out", "east_in")


def place_signals(control):
    x, y, z = train.X, train.Y, train.Z
    for i, (target, block_y, at) in enumerate(LOCATIONS):
        reverse = 1 if i % 2 else -1
        control.commands((
            "/item replace entity @s hotbar.0 with create:track_signal 1",
            f"/tp @s {target + 0.5 + 2 * reverse} {y} {z + 0.5} {90 * reverse} 20",
        ))
        control.call("wait", 3)
        control.call("select", signals.SIGNAL)
        train.click_track(control, target)
        control.command(f"/tp @s {target + 0.5} {y} {at + 1.5}")
        control.call("wait", 3)
        control.call("interact", target, block_y - 1, at, "up")
        control.call("wait", 3)
        if not control.command(f"/execute if block {target} {block_y} {at} {signals.SIGNAL}").startswith("Test passed"):
            raise RuntimeError(f"Train Signal {i} was not placed at {(target, block_y, at)}.")


def run(args):
    with (ROOT / "fixtures/signal-train-occupancy-java.csv").open() as source:
        java = list(csv.DictReader(source))
    differences = []
    with fixture_world(args, "Signal-train-occupancy", train.STRUCTURE, render=True, pack=args.pack) as control:
        train.setup(control, after_station=place_signals)
        start = control.clock()
        first = int(java[0]["tick"])
        for row in java:
            tick = int(row["tick"])
            if tick > first:
                control.step_to(start + tick - first)
            train_state = train.sample(control)
            for key, value in zip(("speed", "wheel_1", "wheel_2", "wheel_3", "wheel_4"), train_state[:5], strict=True):
                if not isclose(value, float(row[key]), rel_tol=0, abs_tol=1.2e-6):
                    differences.append(f"{tick} train {key} {value} vs {row[key]}")
            state = control.commands(f"/data get block {signals.coords(pos)} State" for pos in LOCATIONS)
            for name, data in zip(KEYS, state, strict=True):
                value = re.search(r'"([A-Z]+)"$', data)[1]
                if value != row[name]:
                    differences.append(f"{tick}/{name} {value} vs {row[name]}")
            binding = {18: ("w", "down"), 49: ("w", "up"), 84: ("s", "down"), 110: ("s", "up")}.get(tick)
            if binding:
                control.call("key", *binding)
                control.call("wait", 3)
    if differences:
        raise RuntimeError(f"{len(differences)} train occupancy differences. " + "; ".join(differences[:32]))
    print(f"All {len(java)} Java train movement ticks and four signal lamps per tick matched.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
