#!/usr/bin/env python3
"""Recover an unreachable scheduled route and a manually canceled trip."""

import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from fixture_world import fixture_world

trip = import_module("test-scheduled-station-approach")
conductor = trip.conductor
train = conductor.train
GUEST = "RouteGuest"
PROGRAM = ('{"create:train_schedule":{Cyclic:0b,Entries:[{Instruction:{Id:"create:destination",'
           'Data:{Text:"Terminal"}},Conditions:[]}]}}')


def value(world, field, observer=None):
    """Read route state through the observing client when one is supplied."""
    observer = observer or world
    command = f"/data get entity {train.ENTITY} CreateTrain.{field}"
    if observer is world:
        reply = observer.command(command)
    else:
        observer.call("chat", command)
        observer.call("wait", 2)
        messages = observer.call("messages")["chat"]
        reply = next(
            (item if isinstance(item, str) else item.get("message", "")
             for item in reversed(messages) if "entity data:" in (item if isinstance(item, str) else item.get("message", ""))),
            "",
        )
        if not reply:
            raise RuntimeError(f"Guest did not return route state for {field}: {messages}")
    return reply.partition("entity data: ")[2]


def advance(world, ticks):
    start = world.clock()
    world.command(f"/tick step {ticks}")
    expected = start + ticks
    deadline = time.monotonic() + 8
    while (current := world.clock()) != expected:
        if current > expected or time.monotonic() >= deadline:
            raise RuntimeError(f"Expected {ticks} stepped ticks from {start}; got {current}.")
        time.sleep(0.05)


def missing_target_then_restore(world, actor, who, observer):
    terminal = trip.approach.DESTINATION
    x, y, z = terminal
    world.command(f'/data merge block {x} {y} {z} {{Name:"Offline"}}')
    conductor.set_held(world, actor, who, conductor.SCHEDULE, components=PROGRAM)
    conductor.click(world, actor, who, 0)
    if conductor.assigned(world) is None:
        raise RuntimeError("The seated conductor did not take the route-recovery timetable.")

    advance(world, 42)
    if value(world, "ApproachStation", observer) or value(world, "SchedulePaused", observer).endswith("1b"):
        raise RuntimeError("An unreachable destination started travel or paused the schedule.")
    if float(value(world, "Speed", observer)[:-1]) != 0.0:
        raise RuntimeError("The train moved while its named destination was unavailable.")

    world.command(f'/data merge block {x} {y} {z} {{Name:"Terminal"}}')
    advance(world, 45)
    if not value(world, "ApproachStation", observer).endswith("[I; " + ", ".join(map(str, terminal)) + "]"):
        raise RuntimeError("The route did not recover after its destination became reachable.")
    if float(value(world, "Speed", observer)[:-1]) <= 0.0:
        raise RuntimeError("The recovered route did not begin moving.")


def cancel_and_resume(world, actor, who, observer):
    # The train starts within one control-block reach of the assembled train.
    # After 45 ticks it has moved along the same straight rail, so use the
    # leading wheel's offset to place the actor beside its mounted controls.
    wheels = train.sample(world)[1:5]
    delta = wheels[0] - 0.5
    cx = train.X + 1.5 + delta
    cz = train.Z + 0.5
    world.command(f"/tp {who} {cx} {train.Y} {train.Z - 1.3}")
    actor.call("wait", 3)
    actor.call("look-at", cx, train.Y + 3.45, cz)
    actor.call("mouse", "right", "click")
    actor.call("wait", 3)

    if not value(world, "SchedulePaused", observer).endswith("1b"):
        raise RuntimeError("Taking controls did not pause the scheduled trip.")
    if value(world, "ScheduleRuntime.Stage", observer) or value(world, "ApproachStation", observer):
        raise RuntimeError("Taking controls left stale in-transit navigation state.")

    actor.call("key", "shift", "down")
    actor.call("wait", 3)
    advance(world, 1)
    actor.call("key", "shift", "up")
    driver_command = f"/data get entity {train.ENTITY} CreateTrain.Driver"
    if observer is world:
        driver_reply = observer.command(driver_command)
    else:
        observer.call("chat", driver_command)
        observer.call("wait", 2)
        driver_reply = "\n".join(
            item if isinstance(item, str) else item.get("message", "")
            for item in observer.call("messages")["chat"]
        )
    if "entity data:" in driver_reply:
        raise RuntimeError("Sneak did not release the canceled trip's train controls.")

    conductor.click(world, actor, who, 0)
    if value(world, "SchedulePaused", observer).endswith("1b"):
        raise RuntimeError("The conductor did not resume the canceled timetable.")
    advance(world, 1)
    if not value(world, "ApproachStation", observer).endswith("[I; " + ", ".join(map(str, trip.approach.DESTINATION)) + "]"):
        raise RuntimeError("The resumed timetable did not redispatch its destination.")


def exercise(world, actor, who, observer=None):
    observer = observer or world
    world.command(f"/attribute {who} minecraft:gravity base set 0")
    missing_target_then_restore(world, actor, who, observer)
    cancel_and_resume(world, actor, who, observer)
    advance(world, 100)
    arrived = value(world, "ArrivedStation", observer)
    expected = "[I; " + ", ".join(map(str, trip.approach.DESTINATION)) + "]"
    if not arrived.endswith(expected):
        raise RuntimeError(f"The recovered timetable did not arrive at Terminal: {arrived}")


def run(args):
    with fixture_world(args, "scheduled-route-recovery", train.STRUCTURE,
                       render=True, pack=args.pack) as world:
        train.setup(world, after_station=trip.place_stations, take_controls=False)
        if not args.multiplayer:
            exercise(world, world, "@s")
            return

        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-route-recovery-") as scratch, conductor.multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST,
            render=True, scenario="scheduled-route-recovery", pack=args.pack,
            launch_timeout=120,
        ) as guest:
            conductor.multiplayer.until("the route-recovery guest to join", lambda: any(
                item["name"] == GUEST and item["placed"] for item in world.call("lan", "status")["guests"]
            ))
            world.command(f"/gamemode survival {GUEST}")
            exercise(world, guest, GUEST, observer=guest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
    print("Unreachable-target retry, manual route cancellation, conductor resume, and arrival passed.")
