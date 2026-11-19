#!/usr/bin/env python3
"""Drive to a facing Track Station by holding the same Space input as Java."""
import argparse
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

train = import_module("test-simple-train")
X, Y, Z = train.X, train.Y, train.Z
DESTINATION = (X - 13, Y, Z + 2)
REVERSE_DESTINATION = (X + 18, Y, Z + 2)
TRACE = "manual_station_approach"


def place_stations(control, *, reverse=False, stations=None):
    if stations is None:
        stations = ((X + 18, -90), (X + 10, 90)) if reverse else ((X - 13, 90), (X - 6, -90))
    for target, yaw in stations:
        offset = 2 if yaw > 0 else -2
        control.commands((
            "/item replace entity @s hotbar.0 with create:track_station 1",
            f"/tp @s {target + 0.5 + offset} {Y} {Z + 0.5} {yaw} 20",
        ))
        control.call("wait", 3)
        control.call("select", "create:track_station")
        train.click_track(control, target)
        control.command(f"/tp @s {target + 0.5} {Y} {Z + 4.5}")
        control.call("wait", 3)
        control.call("interact", target, Y - 1, Z + 2, "up")
        control.call("wait", 3)
        if control.call("block", target, Y, Z + 2)["block"] != "create:track_station":
            raise RuntimeError(f"Could not place the destination station for x={target}.")


def observe(control, destination=DESTINATION):
    speed, *wheels, _ = train.sample(control)
    target, arrived, distance = control.commands(f"/data get entity {train.ENTITY} CreateTrain.{field}"
        for field in ("ApproachStation", "ArrivedStation", "ApproachDistance"))
    expected = "[I; " + ", ".join(map(str, destination)) + "]"
    match = re.search(f"({train.NUMBER})d$", distance) if target.endswith(expected) else None
    return speed, *wheels, int(target.endswith(expected)), int(arrived.endswith(expected)), float(match[1]) if match else 0.0


def run(args):
    trace = "cancel_station_approach" if args.cancel else TRACE
    if args.reverse:
        trace = "reverse_station_approach"
    destination = REVERSE_DESTINATION if args.reverse else DESTINATION
    drive_key = "s" if args.reverse else "w"
    with (ROOT / f"fixtures/{trace}-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    differences = []
    with fixture_world(args, trace.replace("_", "-"), train.STRUCTURE, render=True, pack=args.pack) as control:
        train.setup(control, after_station=lambda world: place_stations(world, reverse=args.reverse),
                    rear_controls=args.reverse)
        control.command("/attribute @s minecraft:gravity base set 0")
        start = control.clock()
        first = int(rows[0]["tick"])
        with (ROOT / f".local/{trace}-horizon.csv").open("w") as out:
            writer = csv.writer(out)
            writer.writerow(rows[0].keys())
            for row in rows:
                tick = int(row["tick"])
                if tick != first:
                    control.step_to(start + tick - first)
                observed = observe(control, destination)
                writer.writerow((tick, *observed))
                for key, actual in zip(tuple(row)[1:], observed, strict=True):
                    if not isclose(actual, float(row[key]), rel_tol=0.0, abs_tol=2e-6):
                        differences.append(f"{tick}/{key} {actual} vs {row[key]}")
                if tick == 24:
                    if args.reverse:
                        control.command(f"/tp @s {X + 1.5} {Y + 4} {Z + 1.5}")
                        control.call("wait", 3)
                    control.call("key", drive_key, "down")
                    control.call("wait", 3)
                if tick == 42:
                    control.call("key", drive_key, "up")
                    control.call("key", "space", "down")
                    control.call("wait", 3)
                if args.cancel and tick == 68:
                    control.call("key", "space", "up")
                    control.call("wait", 3)
                if (26 if args.reverse else 32) <= tick < 105 and tick % 3 == 2:
                    seat_x = X + (observed[1] + observed[2]) / 2
                    control.command(f"/tp @s {seat_x:.6f} {Y + 4} {Z + 1.5}")
                    control.call("wait", 3)
            control.call("key", "space", "up")
        if differences:
            raise RuntimeError(f"{len(differences)} Java approach differences. " + "; ".join(differences[:18]))
        if args.cancel:
            print(f"Manual approach cancellation and coast matched Java on all {len(rows)} ticks.")
            return
        x, y, z = destination
        control.command(f"/tp @s {x + 0.5} {y} {z + 2.5}")
        control.call("wait", 3)
        control.call("interact", x, y, z, "up")
        control.call("wait", 3)
        controls = control.call("ui")["widgets"]
        if not any(widget["id"] == "disassemble-train" and widget["enabled"] for widget in controls):
            raise RuntimeError(f"The destination did not show the arrived train: {controls}")
        control.call("click-button", "Disassemble Train")
        control.call("wait", 3)
        direction = -1 if args.reverse else 1
        landed = control.call("block", x + direction, Y + 1, Z)["block"]
        old = control.call("block", X + 1, Y + 1, Z)["block"]
        if landed != "create:small_bogey" or old != "minecraft:air":
            raise RuntimeError(f"Disassembly restored the train to the wrong rail: arrival {landed}, origin {old}")
        if args.reverse:
            near = control.call("block", x - 1, Y + 3, Z)["state"]
            far = control.call("block", x - 4, Y + 3, Z)["state"]
            if "facing=west" not in near or "facing=east" not in far:
                raise RuntimeError(f"Reverse disassembly had the wrong controls: {near}, {far}")
    print(f"Manual approach and arrival matched Java on all {len(rows)} ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    direction = parser.add_mutually_exclusive_group()
    direction.add_argument("--cancel", action="store_true")
    direction.add_argument("--reverse", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
