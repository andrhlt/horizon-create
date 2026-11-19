#!/usr/bin/env python3
"""Compare which mounted chest a real hopper drains in two Java train layouts."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

schedule = import_module("test-scheduled-station-approach")
train = schedule.train
conductor = schedule.conductor
multiplayer = conductor.multiplayer
AIR = ("minecraft:air", 0)
DECOYS = [(1, "minecraft:paper", 7), (2, "minecraft:redstone", 64)]


def slot_zero(slots):
    return next(((item, count) for slot, item, count in slots if slot == 0), AIR)


def prepare_leading_chest(world, offset):
    position = (train.X + offset, train.Y + 2, train.Z)
    at = schedule.coordinates(position)
    world.commands((f"/setblock {at} minecraft:chest",
                    f"/item replace block {at} container.0 with minecraft:emerald"))


def replay(world, offset, reference):
    world.command("/attribute @s minecraft:gravity base set 0")
    conductor.set_held(world, world, "@s", conductor.SCHEDULE, components=schedule.IDLE_CARGO_PROGRAM)
    conductor.click(world, world, "@s", 0)
    if conductor.assigned(world) is None:
        raise RuntimeError("The train did not take the timetable")
    start = world.clock()
    leading = f"CreateTrain.Blocks[{{Pos:[I;{offset - 1},1,0]}}].VanillaEntity.Items"
    hopper = schedule.coordinates(schedule.hopper_position(False))
    lock = schedule.coordinates(schedule.hopper_lock(False))
    commands = (
        f"/data get entity {train.ENTITY} {leading}",
        f"/data get entity {train.ENTITY} {schedule.CARGO_CHEST}.VanillaEntity.Items",
        f"/data get block {hopper} Items",
        f"/data get entity {train.ENTITY} CreateTrain.CargoIdleTicks",
    )
    for row in reference:
        tick = int(row["tick"])
        world.step_to(start + tick - 22)
        leading_raw, rear_raw, hopper_raw, clock_raw = world.commands(commands)
        front, rear, transfer = map(schedule.chest_slots, (leading_raw, rear_raw, hopper_raw))
        if [item for item in rear if item[0] != 0] != DECOYS:
            raise RuntimeError(f"Rear chest decoys changed at tick {tick}: {rear}")
        clock = int(clock_raw.partition("data: ")[2] or 0)
        actual = (*slot_zero(front), *slot_zero(rear), *slot_zero(transfer), clock)
        expected = tuple(row[key] if key.endswith("_item") else int(row[key])
                         for key in ("leading_item", "leading_count", "rear_item", "rear_count",
                                     "hopper_item", "hopper_count", "cargo_idle_ticks"))
        if actual != expected:
            raise RuntimeError(f"Cargo order differs at tick {tick}. Java {expected}, Horizon {actual}")
        if tick == 27:
            world.command(f"/setblock {lock} minecraft:air")
        elif tick == 28:
            world.command(f"/setblock {lock} minecraft:redstone_block")
    print(f"Mounted chest transfer order matched {len(reference)} original Java ticks.", flush=True)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        cli.add_argument(name, type=Path)
    cli.add_argument("--pack", type=Path)
    cli.add_argument("--layout", choices=("front", "deck"), required=True)
    cli.add_argument("--multiplayer", action="store_true")
    cli.add_argument("--reference", type=Path, default=ROOT / "fixtures/train-chest-order-java.csv")
    args = cli.parse_args()
    with args.reference.open(newline="") as source:
        reference = [row for row in csv.DictReader(source) if row["layout"] == args.layout]
    assert len(reference) == 6, reference
    offset = 1 if args.layout == "front" else 3
    scenario = f"train-chest-order-{args.layout}" + ("-lan" if args.multiplayer else "")
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, scenario, train.STRUCTURE, render=True, pack=args.pack))
        train.setup(world, after_station=schedule.place_hopper_cargo_stations,
                    before_glue=lambda world: prepare_leading_chest(world, offset), take_controls=False)
        guest = None
        if args.multiplayer:
            who = "CargoOrderGuest"
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-cargo-")))
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", who, render=True, scenario=scenario, pack=args.pack,
            ))
            multiplayer.until("the cargo guest to join", lambda: any(
                player["name"] == who and player["placed"] for player in world.call("lan", "status")["guests"]
            ))
            hx, hy, hz = schedule.hopper_position(False)
            parking = (hx + 0.5, hy, hz + 2.5)
            world.commands((f"/gamemode survival {who}", f"/attribute {who} minecraft:gravity base set 0",
                            f"/tp {who} {schedule.coordinates(parking)}"))
            multiplayer.until("the cargo guest to reach the Hopper", lambda:
                              tuple(guest.call("state")["player"]["position"]) == parking)
            multiplayer.until("the cargo guest to see the Hopper", lambda:
                              guest.call("block", hx, hy, hz)["block"] == "minecraft:hopper")
        replay(world, offset, reference)
        if guest:
            wanted = reference[-1]["hopper_item"]
            count = int(reference[-1]["hopper_count"])
            guest.call("interact", hx, hy, hz, "south")
            multiplayer.until("the cargo guest to see the transferred stack", lambda: any(
                (entry["stack"] or {}).get("item") == wanted and entry["stack"]["count"] == count
                for entry in guest.call("menu")["slots"]
            ))
            print(f"The LAN guest saw {count} {wanted} in the Hopper.", flush=True)



if __name__ == "__main__":
    main()
