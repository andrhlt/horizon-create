#!/usr/bin/env python3
"""Pass a saved Train Schedule to real assembled-carriage Seat occupants."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

train = import_module("test-simple-train")
entry = import_module("test-train-schedule-entry")
multiplayer = import_module("test-multiplayer")
X, Y, Z = train.X, train.Y, train.Z
SEATS = (X + 2, X + 4)
SCHEDULE = "create:schedule"
GUEST = "ConductorGuest"
PROGRAM = ('{Cyclic:1b,Entries:[{Instruction:{Id:"create:destination",Data:{Text:"No Such Station"}},'
           'Conditions:[[{Id:"create:delay",Data:{TimeUnit:1,Value:5}}]]}]}')
SAVED = '{"create:train_schedule":' + PROGRAM + ',"minecraft:custom_name":{text:"Route Master"}}'
EMPTY_SAVED = '{"create:train_schedule":{Cyclic:1b,Entries:[]}}'


def scenario_setup(world):
    for x in SEATS:
        world.commands((
            f"/setblock {x} {Y + 2} {Z} minecraft:oak_planks",
            f"/setblock {x} {Y + 3} {Z} create:white_seat",
            f"/summon minecraft:villager {x + .5} {Y + 3.65} {Z + .5} {{Motion:[0d,-0.35d,0d]}}",
        ))
    for _ in range(2):
        world.step_to(world.clock() + 1)
    for x in SEATS:
        rider = f"@e[type=minecraft:villager,limit=1,sort=nearest,x={x + 0.5},y={Y + 3},z={Z + 0.5}]"
        marker = world.command(f"/data get entity {rider} CreateSeat")
        if not marker.endswith(f"[I; {x}, {Y + 3}, {Z}]"):
            raise RuntimeError(f"The villager at {x} did not sit in the static Seat: {marker}")


def assigned(world):
    raw = world.command(f"/data get entity {train.ENTITY} CreateTrain.Schedule")
    if "entity data: " not in raw:
        return None
    return entry.snbt(raw.split("entity data: ", 1)[1])


def set_held(world, actor, who, kind, count=1, components=None):
    world.command(f'/item replace entity {who} hotbar.0 with {kind if components is None else "minecraft:air"} {count}')
    actor.call("key", "1", "tap")
    actor.call("wait", 3)
    if components is None:
        return
    world.command(f'/execute at {who} run summon minecraft:item ~ ~ ~ {{Item:{{id:"{kind}",count:{count},components:{components}}},PickupDelay:0s,Motion:[0d,0d,0d]}}')
    world.step_to(world.clock() + 1)
    multiplayer.until("the dropped Schedule to be in hand", lambda: held_count(actor) == count)


def held_count(actor):
    bar = next(item for item in actor.call("inventory")["hotbar"] if item["slot"] == 0)
    return int(bar.get("count") or 0)


def click(world, actor, who, seat, *, from_north=False):
    x = SEATS[seat] + 0.5
    approach_z = Z - 1.65 if from_north else Z + 2.65
    world.command(f"/tp {who} {x} {Y + 3} {approach_z}")
    actor.call("wait", 3)
    actor.call("look-at", x, Y + 4.25, Z + 0.5)
    start = world.clock()
    actor.call("mouse", "right", "click")
    actor.call("wait", 5)
    if world.clock() != start:
        raise RuntimeError("The conductor click advanced the simulation clock.")


def compare(world, actor, row):
    found = held_count(actor), assigned(world) is not None
    expected = int(row["held_count"]), row["assigned"] == "true"
    if found != expected:
        raise RuntimeError(f"{row['action']}: Horizon hand and assigned state {found} vs. Java {expected}")


def exercise(world, actor, who, expected):
    world.command(f"/attribute {who} minecraft:gravity base set 0")
    cases = (
        ("ordinary_seat", 1, SCHEDULE, 2, SAVED),
        ("blank", 0, SCHEDULE, 1, None),
        ("empty_entries", 0, SCHEDULE, 1, EMPTY_SAVED),
        ("assign", 0, SCHEDULE, 2, SAVED),
        ("again", 0, SCHEDULE, 1, SAVED),
        ("ordinary_empty", 1, "minecraft:air", 1, None),
        ("occupied_hand", 0, "minecraft:paper", 1, None),
        ("resume", 0, "minecraft:air", 1, None),
        ("remove", 0, "minecraft:air", 1, None),
    )
    for action, seat, kind, count, components in cases:
        # Player cooldowns advance even as the fixture holds level ticks.
        actor.call("wait", 5)
        set_held(world, actor, who, kind, count, components)
        if action == "resume":
            world.command(f"/data modify entity {train.ENTITY} CreateTrain.SchedulePaused set value 1b")
        click(world, actor, who, seat)
        compare(world, actor, expected[action])
        if action == "assign" and assigned(world) != entry.snbt(PROGRAM):
            raise RuntimeError("The saved Schedule data changed when assigned.")
        if action == "resume" and "entity data: " in world.command(
                f"/data get entity {train.ENTITY} CreateTrain.SchedulePaused"):
            raise RuntimeError("An empty-hand conductor interaction removed a paused trip without first resuming it.")
    returned = entry.selected_schedule(world, who)
    if returned != entry.snbt(PROGRAM) or "Route Master" in world.command(f"/data get entity {who} SelectedItem"):
        raise RuntimeError(f"The returned Schedule changed its data or kept the source custom name: {returned}")


def run(args):
    with (ROOT / "fixtures/train-conductor-java.csv").open() as source:
        expected = {row["action"]: row for row in csv.DictReader(source)}
    scenario = "train-conductor-lan" if args.multiplayer else "train-conductor"
    with fixture_world(args, scenario, train.STRUCTURE, render=True, pack=args.pack) as world:
        train.setup(world, after_station=scenario_setup, take_controls=False)
        carriage = world.command(f"/data get entity {train.ENTITY} CreateTrain.Blocks")
        if carriage.count("SeatOccupant") != 2 or carriage.count("ConductorDirections") != 1:
            raise RuntimeError(f"The two occupied train Seats did not assemble correctly: {carriage}")
        if args.multiplayer:
            port = world.call("lan", "open", "0", "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-conductor-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST,
                render=True, scenario=scenario, pack=args.pack,
            ) as guest:
                multiplayer.until("the conductor test guest to join", lambda: any(
                    link["name"] == GUEST and link["placed"] for link in world.call("lan", "status")["guests"]
                ))
                world.command(f"/gamemode survival {GUEST}")
                exercise(world, guest, GUEST, expected)
        else:
            exercise(world, world, "@s", expected)
    print("Real assembled-carriage Seat interactions match nine Java hand and assignment observations.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
