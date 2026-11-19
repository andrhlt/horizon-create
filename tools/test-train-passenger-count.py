#!/usr/bin/env python3
"""Compare the original departure waits for exact and minimum train passenger counts."""

import argparse
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

riders = import_module("test-multiplayer-train-seats")
schedule = riders.schedule
PROGRAM = schedule.PROGRAM.replace(
    '{Data:{TimeUnit:0,Value:3},Id:"create:delay"}',
    '{Data:{Count:1,Exact:0},Id:"create:player_count"},'
    '{Data:{Count:0,Exact:1},Id:"create:player_count"}',
)


def exercise(host, guest, host_name, rows):
    host.command("/team add TrainSeatProbe")
    host.command("/team modify TrainSeatProbe collisionRule never")
    for name in (host_name, riders.GUEST):
        host.command(f"/team join TrainSeatProbe {name}")
        host.command(f"/attribute {name} minecraft:gravity base set 0")
    host.command("/scoreboard objectives add elevator_ride dummy")
    riders.conductor.set_held(host, host, "@s", riders.conductor.SCHEDULE, components=PROGRAM)
    riders.conductor.click(host, host, "@s", 0)
    if riders.conductor.assigned(host) is None:
        raise RuntimeError("The conductor did not take the passenger-count timetable.")
    riders.mount(host, host, host_name, 3)
    riders.mount(host, guest, riders.GUEST, 4)
    start = host.clock()
    differences = []
    samples = []
    for row in rows:
        tick = int(row["tick"])
        host.step_to(start + tick - 22)
        motion = schedule.observe(host, None, None, None)
        present = sum(riders.elevator.ride(host, name) for name in (host_name, riders.GUEST))
        tag = host.command(f"/data get entity {riders.train.ENTITY} CreateTrain.ScheduleRuntime.Wait[0]")
        progress = int(tag.split("entity data: ")[-1]) if "entity data: " in tag else 0
        observed = (*motion, present, progress)
        samples.append((tick, *observed))
        for (key, expected), actual in zip(list(row.items())[1:], observed, strict=True):
            same = actual == expected if isinstance(actual, str) else isclose(
                actual, float(expected), rel_tol=0, abs_tol=2e-6
            )
            if not same:
                differences.append(f"{tick}/{key}: {actual} != {expected}")
        if tick == 39:
            host.command(f"/ride {riders.GUEST} dismount")
            guest.call("wait", 4)

    with (ROOT / ".local/passenger-count-horizon.csv").open("w") as output:
        writer = csv.writer(output)
        writer.writerow(rows[0])
        writer.writerows(samples)
    if differences:
        raise RuntimeError(f"{len(differences)} Java differences. " + "; ".join(differences[:12]))
    print(f"Exact and minimum passenger waits matched {len(rows)} Java ticks with a real host and guest.")


def run(args):
    with (ROOT / "fixtures/scheduled_player_count-java.csv").open() as trace:
        rows = list(csv.DictReader(trace))
    scenario = "Passenger-count"
    with fixture_world(args, scenario, riders.train.STRUCTURE, render=True, pack=args.pack) as host:
        riders.train.setup(host, after_station=riders.setup, take_controls=False)
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        host_name = host.call("lan", "status")["host"]
        with TemporaryDirectory(prefix="hc-passenger-count-") as scratch, riders.multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", riders.GUEST,
            render=True, scenario=scenario, pack=args.pack,
        ) as guest:
            riders.multiplayer.until("the timetable rider to join", lambda: any(
                player["name"] == riders.GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.command(f"/gamemode survival {riders.GUEST}")
            exercise(host, guest, host_name, rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
