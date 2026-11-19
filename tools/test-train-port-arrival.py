#!/usr/bin/env python3
"""Replay the train's opening connection at a second stationary fluid port.

Apply the Java patches listed by test-train-port-departure.py, then apply
java-train-port-arrival-trace.patch. Create the same fresh scratch save and
run ./gradlew -PparityMovingDeparture -PparityMovingArrival runClient.
Add -PparityActiveArrival for the pre-powered pump and empty receiver tank.
Use -PparityMovingItemArrival for the paired item interface variant or
-PparityFastArrival to move the receiver into the high-speed part of the route.
The authority trace starts at the first positive speed and the client pose
trace starts at the local cell crossing.
"""

import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

departure = import_module("test-train-port-departure")
moving, schedule, train, conductor = departure.moving, departure.schedule, departure.train, departure.conductor
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
RECEIVER = (schedule.approach.DESTINATION[0] + 3, train.Y + 3, train.Z + 2)
FAST_RECEIVER = (train.X - 3, RECEIVER[1], RECEIVER[2])


def reference(scene, name):
    with (FIXTURES / f"train_port_{scene}{name}-java.csv").open() as stream:
        return list(csv.DictReader(stream))


def setup(world, active, kind, receiver):
    x, y, z = receiver
    schedule.place_train_fluid_port(world)
    if kind == "portable_storage_interface":
        world.commands((
            f"/setblock {schedule.coordinates(moving.PORT)} create:{kind}[facing=south]",
            f"/setblock {schedule.coordinates(schedule.PORTABLE_FLUID_POS)} create:{kind}[facing=north]",
        ))
    world.command(f"/setblock {x} {y} {z} create:{kind}[facing=north]")
    if active:
        world.commands((
            f"/setblock {x + 1} {y} {z} create:mechanical_pump[facing=east]",
            f"/setblock {x + 2} {y} {z} create:glass_fluid_pipe[axis=x]",
            f"/setblock {x + 3} {y} {z} create:fluid_tank",
            f"/setblock {x + 1} {y + 1} {z} create:cogwheel[axis=x]",
            f"/setblock {x} {y + 1} {z} create:creative_motor[facing=east]",
        ))


def numeric(reply):
    value = reply.partition(" data: ")[2]
    return float(value.removesuffix("d").removesuffix("f")) if value else 0.0


def observe(world, active, receiver):
    x, y, z = receiver
    fixed = [f"/data get block {x} {y} {z} {field}" for field in ("Timer", "Distance", "TrainPort")]
    queries = [
        f"/data get entity {train.ENTITY} Pos[0]",
        f"/data get entity {train.ENTITY} CreateTrain.Speed",
        *fixed,
    ]
    if active:
        queries.extend((
            f"/data get block {x + 1} {y} {z} Speed",
            f"/data get entity {train.ENTITY} {schedule.TRAIN_WATER}",
            f"/data get block {x + 3} {y} {z} TankContent.Fluid.amount",
        ))
    x, speed, timer, distance, port, *cargo = map(numeric, world.commands(queries))
    return (x, speed, int(timer)), distance, 4 <= timer <= 64 and port != 0, cargo


def assert_state(row, origin, sample):
    authority, distance, connected, cargo = sample
    dx = departure.assert_authority(row, origin, authority)
    assert isclose(distance, float(row["distance"]), abs_tol=2e-6), (row, distance)
    assert connected == (row["connected"] == "true"), (row, connected)
    if cargo:
        assert cargo == [float(row[key]) for key in ("pump", "mounted", "sink")], (row, cargo)
    return dx


def start_route(world, actor, who, active, receiver):
    x, y, z = receiver
    world.command(f"/attribute {who} minecraft:gravity base set 0")
    program = schedule.PROGRAMS["train_fixed_port_lifecycle"]
    if actor is world:
        conductor.set_held(world, actor, who, conductor.SCHEDULE, components=program)
    else:
        schedule.give_fixture_schedule(world, actor, who, program)
    conductor.click(world, actor, who, 0)
    assert conductor.assigned(world), "The seated conductor did not take the original timetable."
    world.commands((f"/gamemode spectator {who}", f"/tp {who} {x + 3.5} {y + 2.2} {z + .3}"))
    actor.call("wait", 3)
    actor.call("look-at", x + .5, y + .5, z - .5)
    actor.call("key", "f1", "tap")
    before = observe(world, active, receiver)
    for _ in range(75):
        world.step_to(world.clock() + 1)
        current = observe(world, active, receiver)
        if current[0][1] > 0:
            return before, current
        before = current
    raise RuntimeError("The train did not start the Terminal leg.")


def run(args):
    receiver = FAST_RECEIVER if args.fast_pass else RECEIVER
    scene = "fast_pass" if args.fast_pass else "arrival"
    label = f"train-port-{scene.replace('_', '-')}"
    if args.item:
        label = "train-port-item-arrival"
    if args.active_receiver:
        label += "-active"
    if args.multiplayer:
        label += "-lan"
    kind = "portable_storage_interface" if args.item else "portable_fluid_interface"
    rows = reference(scene, "_active" if args.active_receiver else "")
    poses = {int(row["tick"]): row for row in reference(scene, "_poses")}
    # Actor starts in the middle of its cell and approaches the terminal from the east.
    cell_boundary = receiver[0] - moving.PORT[0] + .5
    arrival = next(int(row["tick"]) for row in rows if float(row["relative_x"]) < cell_boundary)
    with ExitStack() as resources:
        world = resources.enter_context(fixture_world(args, label, train.STRUCTURE, render=True, pack=args.pack))
        train.setup(world, after_station=lambda control: setup(control, args.active_receiver, kind, receiver), take_controls=False)
        actor, who = world, "@s"
        if args.multiplayer:
            scratch = Path(resources.enter_context(TemporaryDirectory(prefix="hc-arrival-guest-")))
            port = world.call("lan", "open", "0", "commands", "force")["port"]
            who = conductor.GUEST
            actor = resources.enter_context(conductor.multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", who, render=True, scenario=label, pack=args.pack,
            ))
            conductor.multiplayer.until("the port observer to join", lambda: any(
                link["name"] == who and link["placed"] for link in world.call("lan", "status")["guests"]
            ))
        before, first = start_route(world, actor, who, args.active_receiver, receiver)
        origin = before[0][0]
        assert_state(rows[0], origin, before)
        assert_state(rows[1], origin, first)
        args.logs.mkdir(parents=True, exist_ok=True)
        measured = 0
        for row in rows[2:]:
            world.step_to(world.clock() + 1)
            dx = assert_state(row, origin, observe(world, args.active_receiver, receiver))
            phase = int(row["tick"]) - arrival
            if phase in poses:
                moving.verify(world, poses[phase], kind, dx)
                measured += 1
                actor.call("wait", 5)
                actor.call("screenshot", args.logs / f"{label}-{phase:+d}.png")
        assert measured == len(poses), (measured, len(poses))
    print(f"Train {scene.replace('_', ' ')} matched {len(rows)} Java authority ticks and {len(poses)} contact-relative poses.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--active-receiver", action="store_true")
    modes.add_argument("--item", action="store_true")
    modes.add_argument("--fast-pass", action="store_true")
    parser.add_argument("--multiplayer", action="store_true")
    parser.add_argument("--logs", type=Path, default=ROOT / ".local")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
