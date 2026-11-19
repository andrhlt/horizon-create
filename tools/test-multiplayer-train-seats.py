#!/usr/bin/env python3
"""Board two moving carriage seats and compare both players against Java."""
import argparse
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

schedule = import_module("test-scheduled-station-approach")
conductor = schedule.conductor
multiplayer = conductor.multiplayer
elevator = import_module("test-multiplayer-elevator")
train = schedule.train
ORIGIN = (train.X, train.Y, train.Z)
GUEST = "TrainGuest"
elevator.GUEST = GUEST
POSITIONS = ("x", "y", "z")


def setup(host, colored=False):
    schedule.place_stations(host)
    x,y,z = ORIGIN
    if colored:
        host.commands(f"/setblock {x + offset} {y + 3} {z} create:{color}_seat"
                      for offset, color in ((2, "red"), (3, "blue"), (4, "green")))
    else:
        host.command(f"/setblock {x + 3} {y + 3} {z} create:white_seat")
    # Keep only the controlling occupant so each test passenger starts with a free seat.
    host.command(f"/kill @e[type=minecraft:villager,x={x+4.5},y={y+3},z={z+.5},distance=..0.75]")
    # A killed villager remains pickable until its twentieth death tick in Java.
    for _ in range(20):
        host.step_to(host.clock() + 1)


def mount(host, actor, who, offset):
    x, y, z = ORIGIN
    elevator.teleport(host, actor, (x + offset + .5, y + 3, z + 2.65))
    actor.call("wait", 3)
    actor.call("look-at", x + offset + .5, y + 3.2, z + .5)
    actor.call("mouse", "right", "click")
    actor.call("wait", 4)
    if not elevator.ride(host, who):
        raise RuntimeError(f"{who} did not board the assembled train seat.")


def physical_position(host, who):
    return tuple(value - origin for value, origin in zip(
        elevator.pos_reply(host.command(f"/data get entity {who} Pos")), ORIGIN, strict=True))


def matches(position, row):
    return all(isclose(value, float(row[axis]), rel_tol=0, abs_tol=2e-6)
               for axis, value in zip(POSITIONS, position, strict=True))


def exercise(host, guest, host_name, rows, departures):
    # Keep the dismounted test players from being pushed by the passing conductor.
    host.command("/team add TrainSeatProbe")
    host.command("/team modify TrainSeatProbe collisionRule never")
    for who in (host_name, GUEST):
        host.command(f"/team join TrainSeatProbe {who}")
        host.command(f"/attribute {who} minecraft:gravity base set 0")
    host.command("/scoreboard objectives add elevator_ride dummy")
    conductor.set_held(host, host, "@s", conductor.SCHEDULE, components=schedule.PROGRAM)
    conductor.click(host, host, "@s", 0)
    if conductor.assigned(host) is None:
        raise RuntimeError("The conductor did not take a saved schedule.")
    mount(host, host, host_name, 3)
    mount(host, guest, GUEST, 4)
    start = host.clock()
    differences = []
    samples = []
    checks = {23, 30, 59, 60, 98, 113, 114, 145}

    def compare(who, row):
        got = physical_position(host, who)
        mounted = elevator.ride(host, who)
        samples.append((row["tick"], who, str(mounted).lower(), *got))
        if mounted != (row["mounted"] == "true") or not matches(got, row):
            differences.append(f"{row['tick']}/{who}: {mounted, got} vs {row}")

    for tick, pair in rows.items():
        host.step_to(start + tick - 22)
        for who, actor, row in zip((host_name, GUEST), (host, guest), pair, strict=True):
            compare(who, row)
            if tick in checks:
                local = tuple(value - origin for value, origin in zip(
                    actor.call("state")["player"]["position"], ORIGIN, strict=True))
                if not matches(local, row):
                    differences.append(f"{tick}/{who} client: {local} vs {row}")
        if tick in departures:
            who = host_name if tick == 59 else GUEST
            host.command(f"/ride {who} dismount")
            compare(who, departures[tick])
            (host if tick == 59 else guest).call("wait", 4)
    with (ROOT / ".local/multiplayer-train-seats-horizon.csv").open("w") as output:
        writer = csv.writer(output)
        writer.writerow(("tick", "rider", "mounted", *POSITIONS))
        writer.writerows(samples)
    if differences:
        raise RuntimeError(f"{len(differences)} Java seat differences. " + "; ".join(differences[:12]))
    print(f"Both real players matched {len(rows)} Java seat ticks and the two dismount poses.")


def run(args):
    rows = {}
    with (ROOT / "fixtures/scheduled_player_seats-java.csv").open() as trace:
        for row in csv.DictReader(trace):
            rows.setdefault(int(row["tick"]), []).append(row)
    with (ROOT / "fixtures/scheduled_player_dismounts-java.csv").open() as trace:
        departures = {int(row["tick"]): row for row in csv.DictReader(trace)}
    scenario = "multiplayer-train-seats"
    with fixture_world(args, scenario, train.STRUCTURE, render=True, pack=args.pack) as host:
        train.setup(host, after_station=lambda world: setup(world, args.colored), take_controls=False)
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        host_name = host.call("lan", "status")["host"]
        with TemporaryDirectory(prefix="hc-train-seats-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST,
            render=True, scenario=scenario, pack=args.pack,
        ) as guest:
            multiplayer.until("the train rider to join", lambda: any(
                link["name"] == GUEST and link["placed"] for link in host.call("lan", "status")["guests"]
            ))
            host.command(f"/gamemode survival {GUEST}")
            exercise(host, guest, host_name, rows, departures)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--colored", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
