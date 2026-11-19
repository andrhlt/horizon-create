#!/usr/bin/env python3
"""Check full-carriage mail ordering and retry at a loaded Postbox."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT, fixture_world

base = import_module("test-train-postbox-import")
trip, train, conductor = base.trip, base.train, base.conductor
Y, Z, PORT, TERMINAL, PACKAGE = base.Y, base.Z, base.PORT, base.TERMINAL, base.PACKAGE


def setup(world):
    base.setup_station_and_cargo(world)
    x, y, z = train.X + 3, Y + 3, Z
    world.command(f"/item replace block {x} {y} {z} container.3 from block 20 112 4 container.0")
    world.commands(f"/item replace block {x} {y} {z} container.{slot} with minecraft:redstone 64" for slot in range(4, 27))


def run(args):
    base.configure_positions()
    with (ROOT / "fixtures/train-postbox-full-java.csv").open() as source:
        rows = {int(row["tick"]): row for row in csv.DictReader(source)}
    assert (rows[102]["port_empty"], rows[102]["cargo_empty"]) == ("false", "true")
    assert (rows[122]["port_empty"], rows[122]["cargo_empty"]) == ("false", "true")
    assert (rows[123]["port_empty"], rows[123]["cargo_empty"], rows[123]["cargo_address"]) == ("true", "false", "Elsewhere")
    with fixture_world(args, "TrainFullPostbox", train.STRUCTURE, render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.command("/attribute @s minecraft:gravity base set 0")
        world.command(f"/forceload add {train.X-21} {Z} {train.X+25} {Z}")
        world.command(f"/forceload add {PORT[0]} {PORT[2]}")
        train.setup(world, after_station=setup, take_controls=False)
        chest = world.command(f"/data get entity {train.ENTITY} {trip.CHEST_ITEMS}")
        initial = trip.chest_slots(chest)
        assert len(initial) == 27 and initial[3] == (3, PACKAGE, 1) and "Depot" in chest, chest
        world.command("/attribute @s minecraft:gravity base set 0")
        conductor.set_held(world, world, "@s", conductor.SCHEDULE, components=trip.ITEM_CARGO_PROGRAM)
        conductor.click(world, world, "@s", 0)
        assert conductor.assigned(world) is not None
        world.command("/tp @s 512 120 512")
        start = world.clock()
        for tick in range(23, 124):
            world.step_to(start + tick - 22)
            if tick not in (101, 102, 122, 123):
                continue
            box = world.command(f"/data get block {PORT[0]} {Y} {PORT[2]} Items")
            cargo = world.command(f"/data get entity {train.ENTITY} {trip.CHEST_ITEMS}")
            slots = trip.chest_slots(cargo)
            if tick == 101:
                assert len(slots) == 27 and "Elsewhere" in box and "Depot" in cargo, (tick, box, cargo)
            elif tick in (102, 122):
                station = world.command(f"/data get entity {train.ENTITY} CreateTrain.ArrivedStation")
                assert f"{TERMINAL[0]}, {TERMINAL[1]}, {TERMINAL[2]}" in station, (tick, station)
                assert slots == [slot for slot in initial if slot[0] != 3], (tick, box, cargo)
                assert "Elsewhere" in box and box.count('"Depot"') == 2 and PACKAGE not in cargo, (tick, box, cargo)
            else:
                assert slots == initial, (tick, box, cargo)
                assert "Elsewhere" not in box and box.count('"Depot"') == 2 and "Elsewhere" in cargo, (tick, box, cargo)
        print("Full carriage exported matching mail at tick 102, then imported outgoing mail at tick 123.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    run(parser.parse_args())
