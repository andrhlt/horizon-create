#!/usr/bin/env python3
"""Replay four Train Signals bound across a quarter-turn using real player placement."""

import argparse
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

curved = import_module("test-curved-train")
signals = import_module("test-train-signal")
curved.Z = curved.train.Z = 72
X, Y, Z = curved.X, curved.Y, curved.Z
POSITIONS = (
    (X - 2, Y, Z - 3), (X - 2, Y, Z + 3), (X - 10, Y, Z - 15), (X - 16, Y, Z - 15),
)
NAMES = ("east_in", "east_out", "north_in", "north_out")
BRANCHED_POWER_CHANGES = {20: (3, True), 40: (4, True), 58: (3, False), 77: (4, False),
                           85: (2, True), 99: (2, False)}
POWER_CHANGES = {20: (3, True), 40: (3, False), 53: (2, True), 64: (2, False),
                 73: (3, True), 95: (3, False)}


def place_station(control):
    control.commands((
        "/item replace entity @s hotbar.0 with create:track_station",
        f"/tp @s {X + 2.5} {Y} {Z + 0.5} 90 20",
    ))
    control.call("wait", 3)
    control.call("select", "create:track_station")
    curved.train.click_track(control, X)
    control.command(f"/tp @s {X + 0.5} {Y} {Z + 4.5}")
    control.call("wait", 3)
    control.call("interact", X, Y - 1, Z + 2, "up")
    control.call("wait", 3)
    if control.call("block", X, Y, Z + 2)["block"] != "create:track_station":
        raise RuntimeError("Track Station placement failed.")


def wrench(control):
    x, y, z = POSITIONS[0]
    control.commands((
        "/item replace entity @s hotbar.0 with create:wrench",
        f"/tp @s {x + 0.5} {y} {z + 1.5}",
    ))
    control.call("wait", 3)
    control.call("select", "create:wrench")
    control.call("interact", x, y, z, "up")
    control.call("wait", 3)


def run(args):
    name = "branched_signal_chain" if args.branches else "curved_signal_chain"
    if args.cold:
        name = "cold_curved_signal_chain"
    positions = POSITIONS + (((X - 12, Y, Z + 3),) if args.branches else ())
    names = NAMES + (("west_out",) if args.branches else ())
    changes = BRANCHED_POWER_CHANGES if args.branches else POWER_CHANGES
    with (ROOT / f"fixtures/{name}-java.csv").open() as source:
        expected = list(csv.DictReader(source))
    differences = []
    diagnostics = []
    with fixture_world(args, name, render=True, pack=args.pack) as control:
        curved.layout(control, branching=args.branches)
        for _ in range(7):
            control.step_to(control.clock() + 1)
        place_station(control)
        for _ in range(2 if args.branches or args.cold else 32):
            control.step_to(control.clock() + 1)
        start = control.clock()
        for row in expected:
            tick = int(row["tick"])
            control.step_to(start + tick)
            if tick == 1:
                curved.place_signals(control, branch=args.branches)
            if tick == 8 or (tick == 84 and not args.branches):
                wrench(control)
            if tick in changes:
                index, on = changes[tick]
                block = "redstone_block" if on else "air"
                above = signals.coords(signals.at(positions[index], 0, 1, 0))
                control.command(f"/setblock {above} minecraft:{block}")
            states = curved.signal_lamps(control, branch=args.branches)
            if args.diagnostics:
                tags = control.commands(f"/data get block {signals.coords(pos)}" for pos in positions)
                diagnostics.append(f"{tick}," + ",".join(states) + " " + repr(tags))

            types = control.commands(
                f"/execute if block {signals.coords(pos)} {signals.SIGNAL}[type=cross_signal]"
                for pos in positions
            )
            for name, state, mode_check in zip(names, states, types, strict=True):
                mode = "cross_signal" if mode_check.startswith("Test passed") else "entry_signal"
                pair = (state, mode)
                wanted = (row[name], row[f"{name}_type"])
                if pair != wanted:
                    differences.append(f"{tick}/{name}: {pair} vs {wanted}")
    if args.diagnostics:
        (ROOT / f".local/{name}-diagnostics.log").write_text("\n".join(diagnostics) + "\n")
    if differences:
        raise RuntimeError(f"{len(differences)} curved signal chain differences. " + "; ".join(differences[:24]))
    print(f"Matched all {len(positions)} Java signal states and modes for {len(expected)} ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--diagnostics", action="store_true")
    scenario = parser.add_mutually_exclusive_group()
    scenario.add_argument("--branches", action="store_true")
    scenario.add_argument("--cold", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
