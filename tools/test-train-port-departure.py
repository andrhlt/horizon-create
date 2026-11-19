#!/usr/bin/env python3
"""Compare a moving carriage and its fluid interface during station departure.

Apply java-scheduled-train-fluid-port-trace.patch, java-train-moving-port-trace.patch,
and java-train-port-departure-trace.patch to the pinned Create source. Run
./gradlew -PparityMovingPortPreview=fluid runGameTestServer, then copy
run/train-moving-port-preview-test-server/world to
run/moving-port-client/saves/MovingPortDepartureReference. Launch the integrated
client with ./gradlew -PparityMovingDeparture runClient. The probe starts the
train GameTest at fresh coordinates and captures its active carriage.

Align the authority logs to the first positive speed. Align the client poses
to the first moving frame outside the fixed port's cell.
"""

import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

moving = import_module("test-train-moving-port-render")
schedule = moving.schedule
train = moving.train
conductor = moving.conductor
KIND = "portable_fluid_interface"
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def reference(name):
    with (FIXTURES / f"train_port_departure{name}-java.csv").open() as stream:
        return list(csv.DictReader(stream))


def observe(world):
    replies = world.commands((
        f"/data get entity {train.ENTITY} Pos[0]",
        f"/data get entity {train.ENTITY} CreateTrain.Speed",
        f"/data get block {schedule.coordinates(schedule.PORTABLE_FLUID_POS)} Timer",
    ))
    position, speed = (
        float(reply.split("entity data: ", 1)[1].removesuffix("d")) for reply in replies[:2]
    )
    timer = int(replies[2].split("block data: ", 1)[1])
    return position, speed, timer


def assert_authority(row, origin, authoritative):
    position, speed, timer = authoritative
    actual = position - origin, speed, timer
    expected = float(row["relative_x"]), float(row["speed"]), int(row["timer"])
    assert all(isclose(a, b, rel_tol=0.0, abs_tol=2e-6)
               for a, b in zip(actual, expected, strict=True)), (row, actual)
    return actual[0]


def run(args):
    name = "train-port-departure" + ("-lan" if args.multiplayer else "")
    rows = reference("")
    poses = {int(row["tick"]): row for row in reference("_poses")}
    # The fluid port actor starts in the middle of its scanned cell.
    contact_loss = next(int(row["tick"]) for row in rows if float(row["relative_x"]) < -0.5)
    with ExitStack() as entries:
        world = entries.enter_context(fixture_world(args, name, train.STRUCTURE, render=True, pack=args.pack))
        train.setup(world, after_station=lambda control: moving.setup(control, KIND), take_controls=False)
        actor = world
        who = "@s"
        if args.multiplayer:
            scratch = Path(entries.enter_context(TemporaryDirectory(prefix="hc-departure-guest-")))
            port = world.call("lan", "open", "0", "commands", "force")["port"]
            who = conductor.GUEST
            actor = entries.enter_context(conductor.multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", who, render=True, scenario=name, pack=args.pack,
            ))
            conductor.multiplayer.until("the departure observer to join", lambda: any(
                link["name"] == who and link["placed"] for link in world.call("lan", "status")["guests"]
            ))

        world.command(f"/setblock {moving.POWER} minecraft:air")
        for _ in range(10):
            world.step_to(world.clock() + 1)
        before = observe(world)
        origin = before[0]
        assert_authority(rows[0], origin, before)
        moving.verify(world, poses[-1], KIND)

        # The original train waits for idle cargo before this leg.
        # Start from the Terminal row to isolate departure after settling.
        world.command(f"/attribute {who} minecraft:gravity base set 0")
        program = schedule.PROGRAMS["train_fixed_port_lifecycle"].replace("Cyclic:0b", "Progress:1,Cyclic:0b", 1)
        conductor.set_held(world, actor, who, conductor.SCHEDULE, components=program)
        conductor.click(world, actor, who, 0)
        assigned = conductor.assigned(world)
        assert assigned and assigned["Progress"] == 1, assigned

        x, y, z = moving.PORT
        world.commands((f"/gamemode spectator {who}", f"/tp {who} {x - 3.5} {y + 2.2} {z + 2.3}"))
        actor.call("wait", 3)
        actor.call("look-at", x, y + .5, z + 1.5)
        actor.call("key", "f1", "tap")
        args.logs.mkdir(parents=True, exist_ok=True)
        measured = 0
        for row in rows[1:]:
            world.step_to(world.clock() + 1)
            dx = assert_authority(row, origin, observe(world))
            phase = int(row["tick"]) - contact_loss
            if phase in poses:
                moving.verify(world, poses[phase], KIND, dx)
                measured += 1
                actor.call("wait", 5)
                actor.call("screenshot", args.logs / f"{name}-{phase:+d}.png")
        assert measured == len(poses), (measured, len(poses))
    print(f"Train departure matched {len(rows)} Java authority ticks and {len(poses)} contact-relative poses.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    parser.add_argument("--logs", type=Path, default=ROOT / ".local")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
