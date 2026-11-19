#!/usr/bin/env python3
"""Assign a timetable matching two branch stations and replay the Java choice."""
import argparse
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

approach = import_module("test-curved-station-approach")
conductor = import_module("test-train-conductor")
train = approach.train
X, Y, Z = approach.X, approach.Y, approach.Z
conductor.X, conductor.Y, conductor.Z = X, Y, Z
conductor.SEATS = (X + 2, X + 4)
PROGRAM = ('{"create:train_schedule":{Cyclic:0b,Entries:[{Instruction:{Id:"create:destination",'
           'Data:{Text:"Depot *"}},Conditions:[[{Data:{TimeUnit:0,Value:5},Id:"create:delay"}]]}]}}')
TARGETS = (approach.STATION, approach.STRAIGHT_STATION)
STAGES = ("PRE_TRANSIT", "IN_TRANSIT", "POST_TRANSIT")


def place_stations(world):
    approach.place_competing_destinations(world)
    conductor.scenario_setup(world)
    for pos, label in zip(TARGETS, ("Depot Curve", "Depot Straight"), strict=True):
        x, y, z = pos
        world.command(f'/data merge block {x} {y} {z} {{Name:"{label}"}}')


def place_red_signal(world):
    x, y, z = X - 13, Y, Z - 14
    world.commands((
        f"/setblock {x + 3} {y - 1} {z} minecraft:smooth_stone",
        "/item replace entity @s hotbar.0 with create:track_signal",
        f"/tp @s {x + .5} {y} {z + 2.5} 180 20",
    ))
    world.call("wait", 3)
    world.call("select", "create:track_signal")
    world.call("look-at", x + .5, y + .06, z + .5)
    world.call("mouse", "right", "click")
    world.call("wait", 3)
    world.command(f"/tp @s {x + 3.5} {y} {z + 2.5} 180 20")
    world.call("wait", 3)
    world.call("interact", x + 3, y - 1, z, "up")
    world.call("wait", 3)
    world.command(f"/setblock {x + 3} {y + 1} {z} minecraft:redstone_block")
    for _ in range(7):
        world.step_to(world.clock() + 1)
    if not world.command(f"/data get block {x + 3} {y} {z} State").endswith('"RED"'):
        raise RuntimeError("The shorter branch did not have a forced-red signal.")


def observe(world):
    motion = approach.curved.sample(world)
    target, arrived, distance, stage, entry, done = world.commands(
        f"/data get entity {train.ENTITY} CreateTrain.{field}"
        for field in ("ApproachStation", "ArrivedStation", "ApproachDistance",
                      "ScheduleRuntime.Stage", "ScheduleRuntime.Entry", "ScheduleCompleted")
    )

    def station(reply):
        return next((index for index, pos in enumerate(TARGETS, 1)
                     if reply.endswith("[I; " + ", ".join(map(str, pos)) + "]")), 0)

    def number(reply):
        _, separator, value = reply.partition("entity data: ")
        return int(value) if separator else 0

    target, arrived = station(target), station(arrived)
    remaining = float(distance.rsplit(" ", 1)[-1][:-1]) if target else 0.0
    return (*motion, target, arrived, remaining, STAGES[number(stage)], number(entry),
            int(done.endswith("1b")))


def exercise(world, actor, who, rows, scenario):
    world.command(f"/attribute {who} minecraft:gravity base set 0")
    conductor.set_held(world, actor, who, conductor.SCHEDULE, components=PROGRAM)
    conductor.click(world, actor, who, 0)
    if conductor.assigned(world) is None:
        raise RuntimeError("The seated conductor did not take the timetable.")
    start, first = world.clock(), int(rows[0]["tick"])
    differences = []
    with (ROOT / f".local/{scenario}-horizon.csv").open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(rows[0])
        for row in rows:
            tick = int(row["tick"])
            world.step_to(start + tick - first + 1)
            actual = observe(world)
            writer.writerow((tick, *actual))
            for key, value in zip(tuple(row)[1:], actual, strict=True):
                expected = row[key]
                same = value == expected if key == "stage" else isclose(
                    value, float(expected), rel_tol=0.0, abs_tol=7e-6)
                if not same:
                    differences.append(f"{tick}/{key} {value} vs {expected}")
    if differences:
        raise RuntimeError(f"{len(differences)} Java route differences. " + "; ".join(differences[:18]))
    print(f"Wildcard station choice and train travel matched all {len(rows)} Java ticks.")


def run(args):
    name = "scheduled_route_red_cost" if args.forced_red else "scheduled_route_cost"
    with (ROOT / f"fixtures/{name}-java.csv").open() as trace:
        rows = list(csv.DictReader(trace))
    scenario = name.replace("_", "-") + ("-guest" if args.multiplayer else "")
    with fixture_world(args, scenario, train.STRUCTURE, render=True, pack=args.pack) as world:
        train.setup(world, lambda room: approach.curved.layout(room, branching=True, branch_length=40),
                    after_station=place_stations, take_controls=False)
        if args.forced_red:
            place_red_signal(world)
        if not args.multiplayer:
            exercise(world, world, "@s", rows, scenario)
            return
        guest_name = conductor.GUEST
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-route-cost-") as scratch, conductor.multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", guest_name,
            render=True, scenario=scenario, pack=args.pack,
        ) as guest:
            conductor.multiplayer.until("the wildcard timetable guest to join", lambda: any(
                link["name"] == guest_name and link["placed"] for link in world.call("lan", "status")["guests"]
            ))
            world.command(f"/gamemode survival {guest_name}")
            exercise(world, guest, guest_name, rows, scenario)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--forced-red", action="store_true")
    parser.add_argument("--multiplayer", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
