#!/usr/bin/env python3
"""A LAN guest drives to a station and the host checks the original tick trace."""
import argparse
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

steering = import_module("test-multiplayer-train-steering")
multiplayer = import_module("test-multiplayer")
GUEST = steering.GUEST


def run(args):
    curved = args.curved or args.junction or args.choice
    if curved:
        approach = import_module("test-curved-station-approach")
        trace = "branched_station_approach" if args.junction else "curved_station_approach"
        layout = lambda world: approach.curved.layout(world, branching=args.junction)
        place_destination = approach.place_destination
        end_tick = 142
        if args.choice:
            trace = "junction_station_choice"
            layout = lambda world: approach.curved.layout(world, branching=True, branch_length=40)
            place_destination = approach.place_competing_destinations
            end_tick = 145
    else:
        approach = import_module("test-manual-station-approach")
        trace = "reverse_station_approach" if args.reverse else approach.TRACE
        layout = None
        place_destination = lambda world: approach.place_stations(world, reverse=args.reverse)
        end_tick = 105
    train = approach.train
    x, y, z = approach.X, approach.Y, approach.Z
    drive_key = "s" if args.reverse else "w"
    with (ROOT / f"fixtures/{trace}-java.csv").open() as source:
        rows = [row for row in csv.DictReader(source) if int(row["tick"]) <= end_tick]
    scenario = trace.replace("_", "-") + "-guest"
    with fixture_world(args, scenario, train.STRUCTURE, render=True, pack=args.pack) as host:
        train.setup(host, layout, after_station=place_destination, take_controls=False,
                    rear_controls=args.reverse)
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-approach-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST,
            render=True, scenario=scenario, pack=args.pack,
        ) as guest:
            multiplayer.until("the station guest to join", lambda: any(
                entry["name"] == GUEST and entry["placed"] for entry in host.call("lan", "status")["guests"]
            ))
            steering.take_controls(host, guest, origin=(x, y, z))
            start = host.clock()
            first = int(rows[0]["tick"])
            for row in rows:
                tick = int(row["tick"])
                if tick != first:
                    host.step_to(start + tick - first)
                if args.choice:
                    observed = approach.observe(host, approach.STRAIGHT_STATION)
                elif args.reverse:
                    observed = approach.observe(host, approach.REVERSE_DESTINATION)
                else:
                    observed = approach.observe(host)
                for key, actual in zip(tuple(row)[1:], observed, strict=True):
                    if not isclose(actual, float(row[key]), rel_tol=0.0, abs_tol=7e-6 if curved else 2e-6):
                        raise RuntimeError(f"Guest approach tick {tick}/{key}: {actual} vs Java {row[key]}")
                if tick == 24:
                    if args.reverse:
                        host.command(f"/tp {GUEST} {x + 1.5} {y + 4} {z + 1.5}")
                        guest.call("wait", 3)
                    guest.call("key", drive_key, "down")
                    guest.call("wait", 3)
                if tick == 42:
                    guest.call("key", drive_key, "up")
                    guest.call("key", "space", "down")
                    guest.call("wait", 3)
                if (26 if args.reverse else 32) <= tick < end_tick and tick % 3 == 2:
                    seat_x = x + (observed[1] + observed[4 if curved else 2]) / 2
                    seat_z = z + (observed[3] + observed[6]) / 2 if curved else z
                    host.command(f"/tp {GUEST} {seat_x:.6f} {y + 4} {seat_z + 1.5:.6f}")
                    guest.call("wait", 3)
            guest.call("key", "space", "up")
    print(f"Real LAN guest drove and arrived at the facing station. The host matched all {len(rows)} Java ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    scenario = parser.add_mutually_exclusive_group()
    scenario.add_argument("--curved", action="store_true")
    scenario.add_argument("--junction", action="store_true")
    scenario.add_argument("--reverse", action="store_true")
    scenario.add_argument("--choice", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
