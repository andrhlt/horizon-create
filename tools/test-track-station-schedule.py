#!/usr/bin/env python3
"""Retrieve a progressed Schedule from a genuinely assembled Track Station."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

conductor = import_module("test-train-conductor")
entry = import_module("test-train-schedule-entry")
multiplayer = conductor.multiplayer
train = conductor.train
X, Y, Z = train.STATION
GUEST = "ScheduleReturn"
A, B = "Main Platform", "East Yard"
DELAY = '{Conditions:[[{Data:{TimeUnit:1,Value:5},Id:"create:delay"}]],Instruction:{Data:{Text:"%s"},Id:"create:destination"}}'
PROGRAM = "{Cyclic:1b,Entries:[" + ",".join(DELAY % station for station in (A, B)) + "]}"
ITEM = '{"create:train_schedule":' + PROGRAM + "}"
RETURNED = entry.snbt(PROGRAM) | {"Progress": 1}
DROP = f"@e[type=minecraft:item,limit=1,sort=nearest,x={X + .5},y={Y + .5},z={Z + .5},distance=..1]"
BUTTON = "Retrieve Schedule"


def layout(world):
    conductor.scenario_setup(world)
    world.command(f'/data merge block {X} {Y} {Z} {{Name:"{A}"}}')


def button(actor, enabled):
    multiplayer.until(f"the {BUTTON} button to be {enabled=}", lambda: any(
        btn["label"] == BUTTON and btn["enabled"] == enabled
        for btn in actor.call("screen")["buttons"]
    ))


def open_station(world, actor, who):
    world.command(f"/tp {who} {X + .5} {Y} {Z + 2.5}")
    multiplayer.until("the station block to load", lambda: actor.call("block", X, Y, Z)["block"] == "create:track_station")
    actor.call("wait", 3)
    actor.call("look-at", X + .5, Y + .45, Z + .5)
    actor.call("mouse", "right", "click")
    actor.call("wait", 4)


def progress_at_station(world, actor, who):
    conductor.set_held(world, actor, who, conductor.SCHEDULE, components=ITEM)
    conductor.click(world, actor, who, 0)
    if conductor.assigned(world) != entry.snbt(PROGRAM):
        raise RuntimeError("The real conductor did not accept the new two-entry Schedule.")
    target = world.clock() + 110
    world.command("/tick step 110")
    multiplayer.until("the five-second dwell and row transition", lambda: world.clock() == target)
    index = world.command(f"/data get entity {train.ENTITY} CreateTrain.ScheduleRuntime.Entry")
    if not index.endswith("entity data: 1"):
        raise RuntimeError(f"The first row did not complete at the station: {index}")


def exercise(world, actor, who, expected):
    world.command(f"/attribute {who} minecraft:gravity base set 0")
    open_station(world, actor, who)
    button(actor, False)
    actor.call("key", "esc", "tap")
    actor.call("wait", 3)
    for occupied in (False, True):
        progress_at_station(world, actor, who)
        if occupied:
            conductor.set_held(world, actor, who, "minecraft:paper")
        open_station(world, actor, who)
        button(actor, True)
        start = world.clock()
        actor.call("click-button", BUTTON)
        multiplayer.until("the station to detach its Schedule", lambda: conductor.assigned(world) is None)
        if world.clock() != start:
            raise RuntimeError("Retrieval advanced the level clock.")
        row = expected["occupied_hand" if occupied else "empty_hand"]
        selected = world.command(f"/data get entity {who} SelectedItem")
        if row["hand_item"] not in selected:
            raise RuntimeError(f"Retrieval changed the wrong hand item: {selected}")
        dropped = world.command(f'/data get entity {DROP} Item.components."create:train_schedule"')
        if occupied:
            found = entry.snbt(dropped.split("entity data: ", 1)[1])
            at, motion = world.commands(f"/data get entity {DROP} {field}" for field in ("Pos", "Motion"))
            if found != RETURNED or not at.endswith(f"[{X+.5}d, {Y+.5}d, {Z+.5}d]") or not motion.endswith("[0.0d, 0.0d, 0.0d]"):
                raise RuntimeError(f"The station-center Schedule did not retain Java progress or zero motion: {found}, {at}, {motion}")
        elif entry.selected_schedule(world, who) != RETURNED or "entity data: " in dropped:
            raise RuntimeError("The empty-hand case did not return the exact progressed Schedule to inventory.")
        actor.call("key", "esc", "tap")
        actor.call("wait", 3)


def run(args):
    with (ROOT / "fixtures/track-station-schedule-java.csv").open() as source:
        expected = {entry["case"]: entry for entry in csv.DictReader(source)}
    scenario = "Station-schedule-LAN" if args.multiplayer else "Station-schedule"
    with fixture_world(args, scenario, train.STRUCTURE, render=True, pack=args.pack) as world:
        train.setup(world, after_station=layout, take_controls=False)
        if not args.multiplayer:
            exercise(world, world, "@s", expected)
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-station-schedule-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True, scenario=scenario, pack=args.pack,
        ) as guest:
            multiplayer.until("the Schedule retrieval guest", lambda: any(
                link["name"] == GUEST and link["placed"] for link in world.call("lan", "status")["guests"]
            ))
            world.command(f"/gamemode survival {GUEST}")
            world.command(f"/tp @s {X + 4.5} {Y} {Z + 3.5}")
            exercise(world, guest, GUEST, expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
    print("Track Station retrieving returned the progressed Schedule to the player or its own center exactly as in Java.")
