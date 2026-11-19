#!/usr/bin/env python3
"""Compare two station dwell alternatives with the original Java runtime."""
import argparse
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

conductor = import_module("test-train-conductor")
entry = import_module("test-train-schedule-entry")
train = conductor.train
STAGES = ("PRE_TRANSIT", "IN_TRANSIT", "POST_TRANSIT")


def program():
    rows = []
    for groups in (((2, 3), (8,)), ((6,), (2, 6))):
        alternatives = ",".join("[" + ",".join(
            '{Data:{TimeUnit:0,Value:%s},Id:"create:delay"}' % ticks for ticks in series
        ) + "]" for series in groups)
        rows.append('{Conditions:[' + alternatives +
                    '],Instruction:{Data:{Text:"Waiting Station"},Id:"create:destination"}}')
    return "{Cyclic:0b,Entries:[" + ",".join(rows) + "]}"


def layout(world):
    conductor.scenario_setup(world)
    where = " ".join(map(str, train.STATION))
    world.command(f'/data merge block {where} {{Name:"Waiting Station"}}')


def observe(world):
    replies = world.commands(f"/data get entity {train.ENTITY} CreateTrain.{field}" for field in (
        "ScheduleRuntime.Stage", "ScheduleRuntime.Entry", "ScheduleRuntime.Wait",
        "SchedulePaused", "ScheduleCompleted",
    ))
    stage, index, progress, paused, completed = (
        reply.partition("entity data: ")[2] for reply in replies
    )
    stage = STAGES[int(stage or 0)]
    # The Java trace samples condition counters only while waiting at the station.
    waits = [0] * 4
    if stage == "POST_TRANSIT" and progress:
        waits = list(map(int, progress.removeprefix("[I; ").removesuffix("]").split(", ")))
    return (stage, int(index or 0), *waits, str(paused == "1b").lower(),
            str(completed == "1b").lower())


def run(args):
    with (ROOT / "fixtures/train-schedule-groups-java.csv").open() as source:
        expected = list(csv.DictReader(source))
    with fixture_world(args, "train-schedule-groups", train.STRUCTURE, render=True, pack=args.pack) as world:
        train.setup(world, after_station=layout, take_controls=False)
        world.command("/attribute @s minecraft:gravity base set 0")
        timetable = program()
        conductor.set_held(world, world, "@s", conductor.SCHEDULE, components='{"create:train_schedule":' + timetable + "}")
        conductor.click(world, world, "@s", 0)
        if conductor.assigned(world) != entry.snbt(timetable):
            raise RuntimeError("The real conductor rejected the grouped timetable.")
        start = world.clock()
        for row in expected:
            world.step_to(start + int(row["tick"]))
            actual = observe(world)
            reference = (row["stage"], *(int(row[key]) for key in
                                          ("entry", "group_a_step", "group_a_time", "group_b_step", "group_b_time")),
                         row["paused"], row["completed"])
            if actual != reference:
                raise RuntimeError(f"Tick {row['tick']}: Horizon {actual} versus Java {reference}")
        if train.sample(world)[0] != 0:
            raise RuntimeError("Waiting at the current station unexpectedly moved the train.")
    print(f"Two AND/OR wait-condition groups matched Java across all {len(expected)} ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
