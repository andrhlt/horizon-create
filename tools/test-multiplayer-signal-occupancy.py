#!/usr/bin/env python3
"""Verify LAN guest convergence while host drives a signalled junction."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

curved = import_module("test-curved-train")
multiplayer = import_module("test-multiplayer")
train = curved.train
curved.Z = train.Z = 72
curved.Y = train.Y = 180
curved.X = train.X = 8
X, Y, Z = curved.X, curved.Y, curved.Z
train.STATION = (X, Y, Z + 2)
GUEST = "SignalGuest"


def run(args):
    with (ROOT / "fixtures/branched_signal_occupancy-java.csv").open() as source:
        rows = tuple(csv.DictReader(source))
    lamp_positions = ((X - 2, Z - 3), (X - 2, Z + 3),
                      (X - 13, Z - 15), (X - 16, Z - 15),
                      (X - 12, Z + 3), (X - 12, Z - 3))
    with fixture_world(args, "Branched-signal-occupancy-LAN", train.STRUCTURE,
                       render=True, pack=args.pack) as host:
        curved.layout(host, branching=True)
        train.setup(host, lambda _: None, after_station=lambda c: curved.place_signals(
            c, branch=True, both_west=True), take_controls=True)
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-signal-occupancy-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
            scenario="branched-signal-occupancy-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the signal guest to join", lambda: any(
                item["name"] == GUEST and item["placed"]
                for item in host.call("lan", "status")["guests"]
            ))
            start = host.clock()
            first = int(rows[0]["tick"])
            for row in rows:
                tick = int(row["tick"])
                if tick != first:
                    host.step_to(start + tick - first)
                expected = tuple(row[key] for key in (
                    "east_in", "east_out", "north_in", "north_out", "west_out", "west_in"))
                actual = curved.signal_lamps(host, branch=True, both_west=True)
                if actual != expected:
                    raise RuntimeError(f"Host signal state at tick {tick}: {actual} vs {expected}")
                multiplayer.until(
                    f"guest to observe all junction signals at tick {tick}",
                    lambda: all(
                        guest.call("block", x, Y, z)["block"] == "create:track_signal"
                        for x, z in lamp_positions
                    ),
                )
                if tick == 24:
                    host.call("key", "w", "down")
                    host.call("wait", 3)
                elif tick == 98:
                    host.call("key", "w", "up")
                    host.call("wait", 3)
            host.call("key", "w", "up")
    print(f"Host lamps matched {len(rows)} Java ticks and the LAN guest converged on all six signal blocks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())
