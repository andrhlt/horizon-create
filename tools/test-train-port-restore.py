#!/usr/bin/env python3
"""Check a live receiver reacquires the restored train on its first tick.

Capture the pinned Java fixture after motion tick 70, when Timer is 13.
Record the connected state and Timer from the first tick after the loaded
carriage is available. The raw world-clock offset depends on chunk loading.
"""

import argparse
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

arrival = import_module("test-train-port-arrival")
train = arrival.train
receiver = arrival.RECEIVER
reference = Path(__file__).resolve().parent.parent / "fixtures/train_port_restore-java.csv"


def observed_port(world):
    x, y, z = receiver
    timer, owner, last = (
        reply.partition(" data: ")[2] for reply in world.commands(
            f"/data get block {x} {y} {z} {field}"
            for field in ("Timer", "TrainPort", "LastContact")
        )
    )
    return int(timer or "0"), owner, last


def observe_train(world, kind):
    fields = (
        "Pos[0]",
        "CreateTrain.Speed",
        f'CreateTrain.Blocks[{{BlockState:{{Name:"create:{kind}"}}}}].TrainWorkingPos',
    )
    return tuple(reply.partition(" data: ")[2] for reply in world.commands(
        f"/data get entity {train.ENTITY} {field}" for field in fields
    ))


def run(args):
    kind = "portable_storage_interface" if args.item else "portable_fluid_interface"
    tick_to_save = 69 if args.before_contact else 70
    label = f"train-port-{kind.removeprefix('portable_')}-restore-{tick_to_save}"
    with reference.open() as file:
        expected = list(csv.DictReader(file))
    with fixture_world(args, label, train.STRUCTURE, render=True, pack=args.pack) as world:
        train.setup(world, after_station=lambda host: arrival.setup(host, False, kind, receiver), take_controls=False)
        prior, _ = arrival.start_route(world, world, "@s", False, receiver)
        origin = prior[0][0]
        authority = arrival.reference("arrival", "")
        motion_started = world.clock()
        for tick in range(1, tick_to_save + 1):
            world.step_to(motion_started + tick)
            arrival.assert_state(authority[tick + 1], origin, arrival.observe(world, False, receiver))

        saved_tick = world.clock()
        saved_timer, saved_owner, saved_contact = observed_port(world)
        carriage = observe_train(world, kind)
        assert all(carriage), carriage
        if args.before_contact:
            assert (saved_timer, saved_owner, saved_contact) == (0, "", "")
        else:
            assert saved_timer == 13 and saved_owner and saved_contact
        world.call("save")
        world.env["HORIZON_STILL"] = "1"
        world.restart()
        assert world.clock() == saved_tick, world.clock()
        assert observe_train(world, kind) == carriage
        assert observed_port(world) == (saved_timer, "", ""), observed_port(world)

        fresh_owner = None
        for row in expected:
            tick = int(row["tick_from_ready"])
            world.step_to(saved_tick + tick)
            timer, owner, contact = observed_port(world)
            assert timer == int(row["timer"]), (tick, timer, row)
            assert bool(owner and contact) == (row["can_transfer"] == "true"), (tick, owner, contact)
            if fresh_owner is None:
                fresh_owner = owner
            assert owner == fresh_owner, (tick, owner, fresh_owner)
            continuous = authority[tick_to_save + tick + 1]
            current = arrival.observe(world, False, receiver)[0]
            # Keep the original route coordinates independently of the fresh Timer.
            arrival.departure.assert_authority({**continuous, "timer": row["timer"]}, origin, current)
    print(f"Restored receiver matched {len(expected)} Java ticks after carriage availability.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--item", action="store_true")
    parser.add_argument("--before-contact", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
