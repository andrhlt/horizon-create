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


def unoccupied_reopen(args):
    with fixture_world(args, "Signal-unoccupied-reopen", train.STRUCTURE,
                       render=True, pack=args.pack) as control:
        train.setup(control, after_station=place_signals)
        sx, sy, sz = train.STATION
        control.command(f"/tp @s {sx + 0.5} {sy} {sz + 2.5} 180 20")
        control.call("wait", 3)
        control.call("interact", *train.STATION, "up")
        control.call("wait", 4)
        control.call("click-button", "Disassemble Train")
        control.step_to(control.clock() + 1)
        control.call("wait", 3)
        control.call("key", "esc", "tap")
        control.call("wait", 2)
        if control.command(f"/execute if entity {train.ENTITY}").startswith("Test passed"):
            raise RuntimeError("The nominally unoccupied persistence rig still has an assembled train.")

        def states():
            return [
                re.search(r'"([A-Z]+)"$', value)[1]
                for value in control.commands(
                    f"/data get block {signals.coords(pos)} State" for pos in LOCATIONS
                )
            ]

        before = states()
        if before != ["GREEN"] * len(LOCATIONS):
            raise RuntimeError(f"Empty signal sections were not green before save: {before}")
        control.command("/save-all flush")
        control.restart()
        after = states()
        if after != before:
            raise RuntimeError(f"Unoccupied signal states changed across save/reopen: {before} -> {after}")
    print("Unoccupied signal sections stayed clear across idle save/reopen.")


def run(args):
    with (ROOT / "fixtures/signal-train-occupancy-java.csv").open() as source:
        java = list(csv.DictReader(source))
    java_by_tick = {int(row["tick"]): row for row in java}
    differences = []
    if args.reopen:
        unoccupied_reopen(args)
    with fixture_world(args, "Signal-train-occupancy", train.STRUCTURE, render=True, pack=args.pack) as control:
        train.setup(control, after_station=place_signals)
        start = control.clock()
        first = int(java[0]["tick"])
        timeline_shift = 0
        sampled = 0
        for row in java:
            tick = int(row["tick"])
            if tick > first:
                control.step_to(start + tick - first)
            effective_tick = tick + timeline_shift
            if effective_tick not in java_by_tick:
                break
            expected = java_by_tick[effective_tick]
            sampled += 1
            train_state = train.sample(control)
            for key, value in zip(("speed", "wheel_1", "wheel_2", "wheel_3", "wheel_4"), train_state[:5], strict=True):
                if not isclose(value, float(expected[key]), rel_tol=0, abs_tol=1.2e-6):
                    differences.append(f"{effective_tick} train {key} {value} vs {expected[key]}")
            state = control.commands(f"/data get block {signals.coords(pos)} State" for pos in LOCATIONS)
            for name, data in zip(KEYS, state, strict=True):
                value = re.search(r'"([A-Z]+)"$', data)[1]
                if value != expected[name]:
                    differences.append(f"{effective_tick}/{name} {value} vs {expected[name]}")
            if args.reopen and tick == 55:
                # The train is moving inside a signalled section. Client startup
                # advances the live world before control freezes it again.
                if not any(expected[key] == "RED" for key in KEYS) or train_state[0] == 0:
                    raise RuntimeError(f"Active persistence sample at tick {effective_tick} is not occupied.")
                control.command("/save-all flush")
                saved_tick = control.clock()
                control.restart()
                resumed_tick = control.clock()
                elapsed = resumed_tick - saved_tick
                if elapsed < 0:
                    raise RuntimeError(
                        f"Signal save/reopen moved the world clock backward: {saved_tick} -> {resumed_tick}."
                    )
                resume_reference_tick = effective_tick + elapsed
                resumed_row = java_by_tick.get(min(resume_reference_tick, max(java_by_tick)))
                after_train = train.sample(control)
                after_signals = [
                    re.search(r'"([A-Z]+)"$', value)[1]
                    for value in control.commands(
                        f"/data get block {signals.coords(pos)} State" for pos in LOCATIONS
                    )
                ]
                expected_signals = [resumed_row[key] for key in KEYS]
                if after_signals != expected_signals:
                    raise RuntimeError(
                        f"Signal states after occupied save/reopen "
                        f"at Java tick {tick + elapsed}: {after_signals} vs {expected_signals}"
                    )
                expected_train = [float(resumed_row[key]) for key in
                                  ("speed", "wheel_1", "wheel_2", "wheel_3", "wheel_4")]
                if any(not isclose(a, b, rel_tol=0, abs_tol=1.2e-6)
                       for a, b in zip(expected_train, after_train[:5], strict=True)):
                    raise RuntimeError(
                        f"Train motion after occupied save/reopen "
                        f"at Java tick {tick + elapsed}: {after_train} vs {expected_train}"
                    )
                # Client startup can advance the world before the first control
                # request. During the occupied case no controls change; advance
                # the Java phase with the resumed simulation.
                start += elapsed
                timeline_shift += elapsed
            binding = {18: ("w", "down"), 49: ("w", "up"), 84: ("s", "down"), 110: ("s", "up")}.get(effective_tick)
            if binding:
                control.call("key", *binding)
                control.call("wait", 3)
    if differences:
        raise RuntimeError(f"{len(differences)} train occupancy differences. " + "; ".join(differences[:32]))
    if sampled == len(java):
        print(f"All {len(java)} Java train movement ticks and four signal lamps per tick matched.")
    else:
        print(f"Matched {sampled} Java samples and the settled active save/reopen state.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reopen", action="store_true",
                        help="save/reopen once with clear signals and once while occupied")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
