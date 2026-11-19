#!/usr/bin/env python3
"""Exercise curve markers, owner removal, and random-tick expiry headlessly."""

import argparse
import csv
import importlib.util
from pathlib import Path

from fixture_world import ROOT, fixture_world

spec = importlib.util.spec_from_file_location("track_curve", ROOT / "tools/test-track-curve.py")
track_curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(track_curve)


def markers(control):
    positions = [(x, 112, z) for x in range(7, 16) for z in range(-8, 1)]
    replies = control.commands(
        f"/execute if block {x} {y} {z} create:fake_track"
        for x, y, z in positions
    )
    return {pos for pos, reply in zip(positions, replies) if reply.startswith("Test passed")}


def step(control, ticks):
    control.command(f"/tick step {ticks}")
    control.call("wait", ticks + 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    with (ROOT / "fixtures/track_curve-java.csv").open() as file:
        case = next(csv.DictReader(file))
    with fixture_world(args, "Fake-track", track_curve.STRUCTURE, pack=args.pack) as control:
        control.command("/fill -11 111 -24 25 111 7 minecraft:smooth_stone")
        control.command("/gamemode survival")
        control.command("/attribute @s minecraft:gravity base set 0")
        track_curve.test_case(control, case)
        placed = markers(control)
        if not placed:
            raise RuntimeError("Creating the curve did not place any Fake Track markers")
        step(control, 120)
        if markers(control) != placed:
            raise RuntimeError("The live curve did not keep its markers alive")
        control.command("/gamemode creative")
        control.command("/tp @s 5.5 112 -7.5")
        control.call("look-at", 7.5, 112.06, -7.5)
        control.call("mouse", "left", "click")
        step(control, 1)
        remaining = markers(control)
        failures = []
        owner = control.call("block", 7, 112, -8)["state"]
        if owner != "minecraft:air":
            failures.append(f"Physical break did not remove the owner: {owner}")
        elif remaining:
            failures.append(f"Physical break left markers behind: {sorted(remaining)}")
        control.command("/gamemode survival")
        track_curve.test_case(control, case)
        control.command("/setblock 7 112 -8 minecraft:air")
        step(control, 1)
        remaining = markers(control)
        if remaining:
            failures.append(f"Command removal left markers behind: {sorted(remaining)}")
        control.command("/setblock 0 115 0 create:fake_track")
        control.command("/setblock 8 115 0 create:fake_track[waterlogged=true]")
        control.command("/gamerule random_tick_speed 4096")
        step(control, 100)
        state = control.call("block", 0, 115, 0)["state"]
        if state != "minecraft:air":
            failures.append(f"An unrefreshed marker did not expire: {state}")
        wet = control.call("block", 8, 115, 0)["state"]
        if not wet.startswith("minecraft:water"):
            failures.append(f"An expired waterlogged marker did not restore water: {wet}")
        if failures:
            raise RuntimeError("; ".join(failures))
    print("Curve marker placement, refresh, removal and random-tick expiry passed.")


if __name__ == "__main__":
    main()
