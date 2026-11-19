#!/usr/bin/env python3
"""Compare a parked timetable when its station stops entity ticking."""

import argparse
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

trip = import_module("test-scheduled-station-approach")
conductor = trip.conductor
train = conductor.train
X, Y, Z = 9, 112, -2
STATION = (X, Y, Z + 2)
TERMINAL = (X - 13, Y, Z - 2)
WRONG_WAY = (X - 6, Y, Z - 2)
PROGRAM = trip.PROGRAM.replace(
    '{Data:{TimeUnit:0,Value:3},Id:"create:delay"}',
    '{Data:{},Id:"create:unloaded"}',
)
PROBES = (("station_ticket", X + 5, Z + 2), ("rail_ticket", X + 5, Z))


def positions():
    train.Z = Z
    train.STATION = STATION
    conductor.Z = Z
    trip.approach.DESTINATION = TERMINAL


def setup(world):
    world.commands((
        f"/forceload add {X-21} {Z} {X+25} {Z}",
        f"/forceload add {STATION[0]} {STATION[2]}",
    ))
    train.setup(world, after_station=stations, take_controls=False)


def stations(world):
    for (x, y, z), yaw, label in ((TERMINAL, 90, "Terminal"), (WRONG_WAY, -90, "Wrong way")):
        direction = 2 if yaw > 0 else -2
        world.commands((
            "/item replace entity @s hotbar.0 with create:track_station",
            f"/tp @s {x+.5+direction} {Y} {Z+.5} {yaw} 20",
        ))
        world.call("wait", 3)
        world.call("select", "create:track_station")
        train.click_track(world, x)
        world.command(f"/tp @s {x+.5} {y} {z-2.5} 0 20")
        world.call("wait", 3)
        world.call("interact", x, y-1, z, "up")
        world.call("wait", 3)
        if world.call("block", x, y, z)["block"] != "create:track_station":
            raise RuntimeError(f"Could not place {label} at {(x,y,z)}")
        world.command(f'/data merge block {x} {y} {z} {{Name:"{label}"}}')
    world.command(f'/data merge block {STATION[0]} {STATION[1]} {STATION[2]} {{Name:"Origin"}}')
    conductor.scenario_setup(world)


def ticket_ages(world):
    values = world.commands(
        f"/data get entity @e[type=minecraft:item,tag={name},limit=1] Age" for name, _, _ in PROBES
    )
    ages = [re.search(r"entity data: (\d+)s?$", reply) for reply in values]
    if any(age is None for age in ages):
        raise RuntimeError(f"A chunk-ticking marker was unavailable: {values}")
    return tuple(int(age[1]) for age in ages)


def exercise(world, actor, who, rows, mode, output):
    world.command(f"/attribute {who} minecraft:gravity base set 0")
    conductor.set_held(world, actor, who, conductor.SCHEDULE, components=PROGRAM)
    conductor.click(world, actor, who, 0)
    if conductor.assigned(world) is None:
        raise RuntimeError("The seated conductor did not take the timetable.")
    for name, x, z in PROBES:
        world.command(f'/summon minecraft:item {x+.5} {Y+7} {z+.5} '
                      f'{{Item:{{id:"minecraft:gold_nugget",count:1}},PickupDelay:32767s,'
                      f'Age:0s,Motion:[0d,0d,0d],NoGravity:1b,Tags:["{name}"]}}')
    world.command(f"/tp @s {X+.5} {Y} {Z+200.5}")
    if who != "@s":
        world.command(f"/tp {who} {X+.5} {Y} {Z+200.5}")
    start = world.clock()
    first = int(rows[0]["tick"])
    previous_ages = ticket_ages(world)
    differences = {}
    with output.open("w") as handle:
        writer = csv.writer(handle)
        writer.writerow(rows[0])
        for row in rows:
            tick = int(row["tick"])
            world.step_to(start + tick - first + 1)
            route = trip.observe(world, None, None, None)
            ages = ticket_ages(world)
            x, y, z = STATION
            station, state = world.commands((
                f"/data get block {x} {y} {z} Name",
                f"/data get entity {train.ENTITY} CreateTrain.ScheduleRuntime.Wait[0]",
            ))
            loaded = station.endswith('"Origin"')
            wait = re.search(r"entity data: (\d+)$", state)
            actual = (*route, str(loaded).lower(),
                      *(str(age > prior).lower() for age, prior in zip(ages, previous_ages, strict=True)),
                      int(wait[1]) if wait else 0)
            writer.writerow((tick, *actual))
            for (key, expected), value in zip(list(row.items())[1:], actual, strict=True):
                same = value == expected if isinstance(value, str) else isclose(value, float(expected), rel_tol=0, abs_tol=2e-6)
                if not same and key not in differences:
                    differences[key] = f"{tick}/{key}: Horizon {value}, Java {expected}"
            previous_ages = ages
            if tick == 34:
                reply = world.command(f"/forceload remove {STATION[0]} {STATION[2]}")
                if "Unmarked" not in reply:
                    raise RuntimeError(f"The station ticket could not be removed: {reply}")
    if differences:
        raise RuntimeError("First unmatched samples: " + "; ".join(differences.values()))
    print(f"Station entity-tick loss, wait advance, departure, and arrival match all {len(rows)} Java ticks ({mode}).")


def run(args):
    positions()
    with (ROOT / "fixtures" / "scheduled_chunk_unloaded-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    scenario = "schedule-chunk-unloaded"
    if args.multiplayer:
        scenario += "-lan"
    output = args.output or ROOT/".local"/f"{scenario}-horizon.csv"
    with fixture_world(args, scenario, train.STRUCTURE, render=True, pack=args.pack) as world:
        setup(world)
        if not args.multiplayer:
            exercise(world, world, "@s", rows, "solo", output)
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-chunk-ed-") as directory, conductor.multiplayer.joined_client(
            args, Path(directory), f"127.0.0.1:{port}", "ChunkSchedule",
            render=True, scenario=scenario, pack=args.pack,
        ) as guest:
            name = "ChunkSchedule"
            conductor.multiplayer.until("the guest dispatcher", lambda: any(
                link["name"] == name and link["placed"] for link in world.call("lan", "status")["guests"]
            ))
            world.command(f"/gamemode survival {name}")
            exercise(world, guest, name, rows, "LAN", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    parser.add_argument("--output", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
