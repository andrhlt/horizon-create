#!/usr/bin/env python3
"""Verify LAN guest convergence while host drives a signalled junction."""

import argparse
import csv
import math
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
GUEST_LAMP_POSITIONS = {
    "east_in": (X - 2, Z - 3),
    "east_out": (X - 2, Z + 3),
    "north_in": (X - 10, Z - 15),
    "north_out": (X - 16, Z - 15),
    "west_out": (X - 12, Z + 3),
    "west_in": (X - 12, Z - 3),
}


def guest_lamp_state(guest, name):
    x, z = GUEST_LAMP_POSITIONS[name]
    reply = guest.call("chat", f"/data get block {x} {Y} {z} State")
    guest.call("wait", 2)
    messages = guest.call("messages")["chat"]
    for item in reversed(messages):
        message = item if isinstance(item, str) else item.get("message", "")
        if f"{x}, {Y}, {z}" in message:
            for state in ("RED", "YELLOW", "GREEN"):
                if f'"{state}"' in message:
                    return state
    raise RuntimeError(f"Guest did not return the state of {name} at {x} {Y} {z}: reply={reply}, messages={messages}")


def run(args):
    with (ROOT / "fixtures/branched_signal_occupancy-java.csv").open() as source:
        rows = tuple(csv.DictReader(source))
    lamp_positions = ((X - 2, Z - 3), (X - 2, Z + 3),
                      (X - 10, Z - 15), (X - 16, Z - 15),
                      (X - 12, Z + 3), (X - 12, Z - 3))
    with fixture_world(args, "Branched-signal-occupancy-LAN", train.STRUCTURE,
                       render=True, pack=args.pack) as host:
        train.setup(host, lambda c: curved.layout(c, branching=True), after_station=lambda c: curved.place_signals(
            c, branch=True, both_west=True), take_controls=True)
        host.command("/attribute @s minecraft:gravity base set 0")
        host.command(f"/defaultgamemode spectator")
        host.command(f"/setworldspawn {X - 8} {Y + 15} {Z}")
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-signal-occupancy-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
            scenario="branched-signal-occupancy-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the signal guest to join", lambda: any(
                item["name"] == GUEST and item["placed"]
                for item in host.call("lan", "status")["guests"]
            ))
            multiplayer.until("the guest to load the junction signals", lambda: all(
                guest.call("block", x, Y, z)["loaded"]
                for x, z in lamp_positions
            ))
            start = host.clock()
            first = int(rows[0]["tick"])
            guest_transition_checks = 0
            for row in rows:
                tick = int(row["tick"])
                if tick != first:
                    host.step_to(start + tick - first)
                found = curved.sample(host)
                expected = tuple(row[key] for key in (
                    "east_in", "east_out", "north_in", "north_out", "west_out", "west_in"))
                actual = curved.signal_lamps(host, branch=True, both_west=True)
                if actual != expected:
                    raise RuntimeError(f"Host signal state at tick {tick}: {actual} vs {expected}")
                for key, value in zip(curved.KEYS, found, strict=True):
                    if not math.isclose(value, float(row[key]), rel_tol=0.0, abs_tol=7.0e-6):
                        raise RuntimeError(f"Host train {key} at tick {tick}: {value} vs Java {row[key]}")
                multiplayer.until(
                    f"guest to observe all junction signals at tick {tick}",
                    lambda: all(
                        guest.call("block", x, Y, z)["block"] == "create:track_signal"
                        for x, z in lamp_positions
                    ),
                )
                if tick == 13:
                    guest_lamps = ("east_out", "north_out")
                elif tick == 27:
                    guest_lamps = ("east_out",)
                elif tick == 69:
                    guest_lamps = ("east_out",)
                elif tick == 108:
                    guest_lamps = ("north_out",)
                elif tick == 119:
                    guest_lamps = ("east_out", "north_out")
                else:
                    guest_lamps = ()
                for name in guest_lamps:
                    lamp_index = ("east_in", "east_out", "north_in", "north_out", "west_out", "west_in").index(name)
                    expected_state = actual[lamp_index]
                    multiplayer.until(
                        f"guest {name} lamp to reach {expected_state} at tick {tick}",
                        lambda: guest_lamp_state(guest, name) == expected_state,
                    )
                    guest_transition_checks += 1
                if tick == 24:
                    host.call("key", "w", "down")
                    host.call("key", "d", "down")
                    host.call("wait", 3)
                elif tick == 98:
                    host.call("key", "w", "up")
                    host.call("key", "d", "up")
                    host.call("wait", 3)
                if 32 <= tick < 98:
                    seat_x = X + (found[1] + found[4]) / 2
                    seat_z = Z + (found[3] + found[6]) / 2
                    host.command(f"/tp @s {seat_x:.6f} {Y + 4} {seat_z + 1.5:.6f}")
                    host.call("wait", 3)
            host.call("key", "w", "up")
    print(
        f"Host train and six lamps matched {len(rows)} Java ticks; guest matched host lamp states "
        f"at {guest_transition_checks} occupancy transition samples."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())
