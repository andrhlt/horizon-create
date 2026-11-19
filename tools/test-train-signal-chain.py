#!/usr/bin/env python3
"""Replay chained Train Signals responding to redstone and signal mode changes."""

import argparse
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

signals = import_module("test-train-signal")
X, Y, Z = 9, 112, -40
TARGETS = (X - 4, X, X + 5, X)
POSITIONS = [(x, Y, Z + (-3 if index == 3 else 3)) for index, x in enumerate(TARGETS)]


def place(control):
    for index, x in enumerate(TARGETS):
        side = 1 if index == 3 else -1
        control.commands((
            f"/item replace entity @s hotbar.0 with {signals.SIGNAL} 1",
            f"/tp @s {x + 0.5 + side * 2} {Y} {Z + 0.5} {side * 90} 20",
        ))
        control.call("wait", 3)
        control.call("select", signals.SIGNAL)
        control.call("look-at", x + 0.5, Y + 0.06, Z + 0.5)
        control.call("mouse", "right", "click")
        control.call("wait", 3)
        _, _, z = POSITIONS[index]
        control.command(f"/tp @s {x + 0.5} {Y} {z + 1.5}")
        control.call("wait", 3)
        control.call("interact", x, Y - 1, z, "up")
        control.call("wait", 3)
        if not control.command(f"/execute if block {x} {Y} {z} {signals.SIGNAL}").startswith("Test passed"):
            raise RuntimeError(f"Chain placement {index} failed at {(x, Y, z)}.")


def wrench(control, index):
    x, y, z = POSITIONS[index]
    control.commands((
        "/item replace entity @s hotbar.0 with create:wrench 1",
        f"/tp @s {x + 0.5} {y} {z + 1.5}",
    ))
    control.call("wait", 3)
    control.call("select", "create:wrench")
    control.call("interact", x, y, z, "up")
    control.call("wait", 3)


def run(args):
    with (ROOT / "fixtures/train-signal-chain-java.csv").open() as source:
        rows = list(csv.reader(source))[1:]
    differences = []
    with fixture_world(args, "Train-signal-chain", render=True, pack=args.pack) as control:
        control.commands((
            f"/fill {X - 9} {Y - 1} {Z - 6} {X + 15} {Y - 1} {Z + 6} minecraft:smooth_stone",
            f"/fill {X - 8} {Y} {Z} {X + 14} {Y} {Z} create:track[shape=xo]",
            "/gamemode survival",
        ))
        for _ in range(7):
            control.step_to(control.clock() + 1)
        start = control.clock()
        for tick_text, *expected in rows:
            tick = int(tick_text)
            control.step_to(start + tick)
            if tick == 1:
                place(control)
            if tick in (8, 12, 71):
                wrench(control, 1 if tick == 12 else 0)
            index = {20: 2, 39: 2, 53: 3, 56: 2, 64: 3, 86: 2}.get(tick)
            if index is not None:
                block = "redstone_block" if tick in (20, 53, 56) else "air"
                control.command(f"/setblock {signals.coords(signals.at(POSITIONS[index], 0, 1, 0))} minecraft:{block}")
            actual = control.commands(command for pos in POSITIONS for command in (
                f"/data get block {signals.coords(pos)} State",
                f"/execute if block {signals.coords(pos)} {signals.SIGNAL}[type=cross_signal]",
            ))
            for index in range(4):
                actual_state = actual[index * 2].rsplit('"', 2)[-2]
                actual_type = "cross_signal" if actual[index * 2 + 1].startswith("Test passed") else "entry_signal"
                result = [actual_state, actual_type]
                if result != expected[index * 2:index * 2 + 2]:
                    differences.append(f"{tick}/{index} {result} vs {expected[index * 2:index * 2 + 2]}")
    if differences:
        raise RuntimeError(f"{len(differences)} Train Signal chain differences. " + "; ".join(differences[:36]))
    print(f"Matched four Java signal modes and lamp states on all {len(rows)} chain ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
