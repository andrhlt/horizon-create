#!/usr/bin/env python3
"""Approach a Track Station beyond a turn and disassemble on the new axis."""
import argparse
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

curved = import_module("test-curved-train")
train = curved.train
curved.Z = train.Z = 72
X, Y, Z = curved.X, curved.Y, curved.Z
train.STATION = (X, Y, Z + 2)
TRACK = (X - 13, Y, Z - 18)
STATION = (TRACK[0] + 2, Y, TRACK[2])
STRAIGHT_TRACK = (X - 30, Y, Z)
STRAIGHT_STATION = (STRAIGHT_TRACK[0], Y, Z + 2)


def place_destination(control, *, track=TRACK, station=STATION, straight=False):
    x, y, z = track
    approach = (x + 2.5, y, z + 0.5, 90) if straight else (x + 0.5, y, z + 2.5, 180)
    control.commands((
        "/item replace entity @s hotbar.0 with create:track_station",
        f"/tp @s {' '.join(map(str, approach))} 20",
    ))
    control.call("wait", 3)
    control.call("select", "create:track_station")
    control.call("look-at", x + 0.5, y + 0.06, z + 0.5)
    control.call("mouse", "right", "click")
    control.call("wait", 3)
    a, b, c = station
    control.command(f"/tp @s {a + 0.5} {b} {c + 2.5}")
    control.call("wait", 3)
    control.call("interact", a, b - 1, c, "up")
    control.call("wait", 3)
    if control.call("block", *station)["block"] != "create:track_station":
        raise RuntimeError("Could not place the station after the curve.")


def place_competing_destinations(control):
    place_destination(control)
    place_destination(control, track=STRAIGHT_TRACK, station=STRAIGHT_STATION, straight=True)


def observe(control, station=STATION):
    motion = curved.sample(control)
    target, arrived, distance = control.commands(
        f"/data get entity {train.ENTITY} CreateTrain.{field}"
        for field in ("ApproachStation", "ArrivedStation", "ApproachDistance")
    )
    expected = "[I; " + ", ".join(map(str, station)) + "]"
    match = re.search(f"({train.NUMBER})d$", distance) if target.endswith(expected) else None
    return *motion, int(target.endswith(expected)), int(arrived.endswith(expected)), float(match[1]) if match else 0.0


def disassemble(control, *, straight=False):
    x, y, z = STRAIGHT_STATION if straight else STATION
    control.command(f"/tp @s {x + 0.5} {y} {z + 2.5}")
    control.call("wait", 3)
    control.call("interact", x, y, z, "up")
    control.call("wait", 3)
    controls = control.call("ui")["widgets"]
    if not any(widget["id"] == "disassemble-train" and widget["enabled"] for widget in controls):
        raise RuntimeError("The destination station did not show the arrived train.")
    control.call("click-button", "Disassemble Train")
    control.call("wait", 3)
    x, y, z = TRACK
    expected = (
        ((x, y + 1, z + 1), "create:small_bogey", "axis=z"),
        ((x, y + 1, z + 4), "create:small_bogey", "axis=z"),
        ((x, y + 3, z + 1), "create:controls", "facing=south"),
    )
    if straight:
        x, y, z = STRAIGHT_TRACK
        expected = (
            ((x + 1, y + 1, z), "create:small_bogey", "axis=x"),
            ((x + 4, y + 1, z), "create:small_bogey", "axis=x"),
            ((x + 1, y + 3, z), "create:controls", "facing=east"),
        )
    for pos, block, prop in expected:
        actual = control.call("block", *pos)
        if actual["block"] != block or prop not in actual["state"]:
            raise RuntimeError(f"Disassembly at {pos}: wanted {block} with {prop}, got {actual}.")


def run(args):
    trace = "branched_station_approach" if args.junction else "curved_station_approach"
    if args.choice:
        trace = "junction_station_choice"
    elif args.short_curve:
        trace = "junction_station_short_curve"
    station = STRAIGHT_STATION if args.choice else STATION

    place_stations = (
        place_competing_destinations if args.choice or args.short_curve else place_destination
    )

    def layout(world):
        competing = args.choice or args.short_curve
        curved.layout(world, branching=args.junction or competing, branch_length=40 if competing else 20)
        if args.short_curve:
            world.command(f"/fill {X - 13} {Y} {Z - 45} {X - 13} {Y} {Z - 23} minecraft:air")
    with (ROOT / f"fixtures/{trace}-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    differences = []
    with fixture_world(args, trace.replace("_", "-"), train.STRUCTURE, render=True, pack=args.pack) as control:
        train.setup(control, layout, after_station=place_stations)
        control.command("/attribute @s minecraft:gravity base set 0")
        start = control.clock()
        first = int(rows[0]["tick"])
        with (ROOT / f".local/{trace}{'-diag' if args.trace_arrival else ''}-horizon.csv").open("w") as out:
            writer = csv.writer(out)
            writer.writerow(rows[0].keys())
            for row in rows:
                tick = int(row["tick"])
                if tick != first:
                    control.step_to(start + tick - first)
                found = observe(control, station)
                writer.writerow((tick, *found))
                if args.trace_arrival and 126 <= tick <= 138:
                    inputs = control.call("state")
                    tag = control.command(f"/data get entity {train.ENTITY} CreateTrain")
                    station = control.command(f"/data get block {' '.join(map(str, STATION))}")
                    print(f"{tick} keys={inputs.get('keys')} player={inputs['player']['position']} train={tag} station={station}", flush=True)
                for key, value in zip(tuple(row)[1:], found, strict=True):
                    if not isclose(value, float(row[key]), rel_tol=0.0, abs_tol=7e-6):
                        differences.append(f"{tick}/{key}: {value} vs {row[key]}")
                if tick == 24:
                    control.call("key", "w", "down")
                    control.call("wait", 3)
                if tick == 42:
                    control.call("key", "w", "up")
                    control.call("key", "space", "down")
                    control.call("wait", 3)
                if 32 <= tick < 160 and tick % 3 == 2:
                    x = X + (found[1] + found[4]) / 2
                    z = Z + (found[3] + found[6]) / 2
                    control.command(f"/tp @s {x:.6f} {Y + 4} {z + 1.5:.6f}")
                    control.call("wait", 3)
            control.call("key", "space", "up")
        if differences:
            raise RuntimeError(f"{len(differences)} curved station differences. " + "; ".join(differences[:18]))
        disassemble(control, straight=args.choice)
    route = "through the competing junction" if args.choice or args.short_curve else "around the curve"
    print(f"Manual approach {route} matched {len(rows)} Java ticks and disassembly.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    scenario = parser.add_mutually_exclusive_group()
    scenario.add_argument("--junction", action="store_true")
    scenario.add_argument("--choice", action="store_true")
    scenario.add_argument("--short-curve", action="store_true")
    parser.add_argument("--trace-arrival", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
