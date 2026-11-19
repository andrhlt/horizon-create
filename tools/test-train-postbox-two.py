#!/usr/bin/env python3
"""Check same-arrival transfer between two loaded Postboxes."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT, fixture_world

base = import_module("test-train-postbox-import")
trip, train, conductor = base.trip, base.train, base.conductor
Y, Z, PORT, TERMINAL, PACKAGE = base.Y, base.Z, base.PORT, base.TERMINAL, base.PACKAGE
OTHER = (PORT[0], Y, PORT[2] + 1)


def run(args):
    base.configure_positions()
    with (ROOT / "fixtures/train-postbox-two-java.csv").open() as source:
        rows = {int(row["tick"]): row for row in csv.DictReader(source)}
    assert (rows[101]["source_empty"], rows[101]["destination_empty"], rows[101]["cargo_empty"]) == ("false", "true", "true")
    assert (rows[102]["source_empty"], rows[102]["destination_empty"], rows[102]["cargo_empty"]) == ("true", "false", "true")
    with fixture_world(args, "TrainTwoPostboxes", train.STRUCTURE, render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.command("/attribute @s minecraft:gravity base set 0")
        world.command(f"/forceload add {train.X-21} {Z} {train.X+25} {Z}")
        world.command(f"/forceload add {PORT[0]} {PORT[2]}")
        train.setup(world, after_station=base.setup_station_and_cargo, take_controls=False)
        x, y, z = OTHER
        world.command(f"/setblock {x} {y-1} {z} minecraft:smooth_stone")
        world.command(f"/setblock {x} {y} {z} create:white_postbox")
        world.command(f'/data merge block {x} {y} {z} {{Target:{{type:"create:train_station",relative_pos:[I;0,0,-5]}},AddressFilter:"Elsewhere"}}')
        world.step_to(world.clock() + 1)
        chest = world.command(f"/data get entity {train.ENTITY} {trip.CHEST_ITEMS}")
        original = trip.chest_slots(chest)
        assert len(original) == 3 and PACKAGE not in chest, chest
        conductor.set_held(world, world, "@s", conductor.SCHEDULE, components=trip.ITEM_CARGO_PROGRAM)
        conductor.click(world, world, "@s", 0)
        assert conductor.assigned(world) is not None
        world.command("/tp @s 512 120 512")
        start = world.clock()
        for tick in range(23, 103):
            world.step_to(start + tick - 22)
            if tick not in (101, 102):
                continue
            source = world.command(f"/data get block {PORT[0]} {Y} {PORT[2]} Items")
            destination = world.command(f"/data get block {x} {y} {z} Items")
            cargo = world.command(f"/data get entity {train.ENTITY} {trip.CHEST_ITEMS}")
            assert trip.chest_slots(cargo) == original and PACKAGE not in cargo, (tick, cargo)
            assert "Depot" in source and (("Elsewhere" in source) == (tick == 101)), (tick, source)
            assert ("Elsewhere" in destination) == (tick == 102), (tick, destination)
            if tick == 102:
                station = world.command(f"/data get entity {train.ENTITY} CreateTrain.ArrivedStation")
                assert f"{TERMINAL[0]}, {TERMINAL[1]}, {TERMINAL[2]}" in station, station
        game_dir = Path(world._launch[world._launch.index("--game-dir") + 1])
        world.stop()
        path = game_dir / "saves/TrainTwoPostboxes/dimensions/minecraft/overworld/data/horizon/attachments.dat"
        saved = import_module("test-schematic-capture").read_nbt(path)
        ports = saved["data"]["create"]["train_postbox_ports"]["value"]["Ports"]
        buffers = {tuple(port["Pos"]): port for port in ports}
        assert set(buffers) == {PORT, OTHER}, buffers
        for at, address in ((PORT, "Depot"), (OTHER, "Elsewhere")):
            port = buffers[at]
            items = port["OfflineBuffer"]["Items"]
            assert port["Primed"] == 0 and len(items) == 1 and items[0]["components"]["create:package_address"] == address, port
        print("At Java tick 102, the train moved outgoing mail from the first loaded Postbox to the matching second port.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    run(parser.parse_args())
