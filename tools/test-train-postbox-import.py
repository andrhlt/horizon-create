#!/usr/bin/env python3
"""Check a scheduled train imports an outgoing package from an unloaded Postbox."""
import argparse
import csv
import gzip
import struct
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

trip = import_module("test-scheduled-station-approach")
train = trip.train
conductor = trip.conductor
approach = trip.approach
mp = conductor.multiplayer
Y, Z = 112, -3
TERMINAL = (-4, Y, -1)
PORT = (-4, Y, 3)
PACKAGE = "create:cardboard_package_12x12"


def configure_positions():
    train.Z = Z
    train.STATION = (train.X, Y, Z + 2)
    conductor.Z = Z
    approach.Z = Z
    approach.DESTINATION = TERMINAL


def setup_station_and_cargo(world):
    trip.place_cargo_stations(world)
    world.commands((
        "/setblock 20 112 4 minecraft:barrel",
        f'/data merge block 20 112 4 {{Items:[{{Slot:0b,id:"{PACKAGE}",count:1,components:{{"create:package_address":"Elsewhere"}}}}]}}',
        f"/setblock {PORT[0]} {PORT[1]-1} {PORT[2]} minecraft:smooth_stone",
        "/item replace entity @s hotbar.0 with create:white_postbox",
        f"/tp @s {TERMINAL[0]+0.5} {Y} {TERMINAL[2]+2.5} 180 20",
    ))
    world.call("wait", 4)
    world.call("select", "create:white_postbox")
    world.call("look-at", TERMINAL[0]+0.5, Y+0.4, TERMINAL[2]+0.5)
    mp.until("the Terminal station to be targeted", lambda:
             (world.call("looking-at").get("block") or {}).get("pos") == list(TERMINAL))
    world.call("mouse", "right", "click")
    world.call("wait", 4)
    world.command(f"/tp @s {PORT[0]+0.5} {Y} {PORT[2]+2.5}")
    world.call("wait", 4)
    world.call("interact", PORT[0], PORT[1]-1, PORT[2], "up")
    mp.until("the station-bound Postbox to open automatically", lambda:
             world.call("state")["screen"] == "container" and "Frogport Address" in str(world.call("screen")))
    world.call("click-button", "Frogport Address")
    world.call("type", "Depot")
    world.call("click-button", "Confirm")
    mp.until("the Postbox configuration to close", lambda: world.call("state")["screen"] == "playing")
    world.step_to(world.clock() + 1)
    world.command(f"/item replace block {PORT[0]} {Y} {PORT[2]} container.0 from block 20 112 4 container.0")
    world.command(f'/data merge block 20 112 4 {{Items:[{{Slot:0b,id:"{PACKAGE}",count:1,components:{{"create:package_address":"Depot"}}}}]}}')
    world.command(f"/item replace block {PORT[0]} {Y} {PORT[2]} container.1 from block 20 112 4 container.0")
    target = world.command(f"/data get block {PORT[0]} {PORT[1]} {PORT[2]} Target")
    assert "train_station" in target and "0, 0, -4" in target, target


def run(args):
    configure_positions()
    with (ROOT / ("fixtures/train-loaded-mail-import-java.csv" if args.loaded else "fixtures/train-import-mail-java.csv")).open() as source:
        rows = list(csv.DictReader(source))
    first_arrival = next(int(row["tick"]) for row in rows if row["at_station"] == "true")
    assert first_arrival == 102
    if args.rebind:
        with (ROOT / "fixtures/train-postbox-rebind-java.csv").open() as source:
            rebind = {row["phase"]: row for row in csv.DictReader(source)}
        assert rebind["removed"]["station_present"] == "false"
        assert (rebind["restored"]["same_identity"], rebind["restored"]["address"], rebind["restored"]["buffer_address"]) == ("true", "Depot", "Elsewhere")
    if args.dwell:
        with (ROOT / "fixtures/train-loaded-dwell-import-java.csv").open() as source:
            dwell = {int(row["tick"]): row for row in csv.DictReader(source)}
        assert (dwell[122]["port_empty"], dwell[122]["cargo_empty"]) == ("false", "true")
        assert (dwell[123]["port_empty"], dwell[123]["cargo_empty"], dwell[123]["address"]) == ("true", "false", "Later")
    with fixture_world(args, "TrainOfflineMail", train.STRUCTURE, render=True,
                       pack=args.pack, env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.command(f"/forceload add {train.X-21} {Z} {train.X+25} {Z}")
        if args.loaded:
            world.command(f"/forceload add {PORT[0]} {PORT[2]}")
        train.setup(world, after_station=setup_station_and_cargo, take_controls=False)
        if args.rebind:
            # Replace the station's actual targeted rail, as in the Java oracle.
            world.command(f"/setblock {TERMINAL[0]} {Y} {Z} minecraft:air")
            for _ in range(10):
                world.step_to(world.clock() + 1)
            world.command(f"/setblock {TERMINAL[0]} {Y} {Z} create:track[shape=xo]")
            for _ in range(30):
                world.step_to(world.clock() + 1)
            live = world.command(f"/data get block {PORT[0]} {Y} {PORT[2]} Items")
            assert "Elsewhere" in live and "Depot" in live, live
        path = Path(world._launch[world._launch.index("--game-dir") + 1]) / "saves/TrainOfflineMail/dimensions/minecraft/overworld/data/horizon/attachments.dat"
        destination = PORT if args.loaded else (5000, Y, 5000)
        if not args.loaded:
            # The Java oracle has a real scheduled train and a synthetic
            # registered port at this unloaded position; reproduce that seam.
            world.stop()
            raw = gzip.decompress(path.read_bytes())
            prefix = b"\x0b\x00\x03Pos\x00\x00\x00\x03"
            old = prefix + struct.pack(">iii", *PORT)
            assert raw.count(old) == 1
            path.write_bytes(gzip.compress(raw.replace(old, prefix + struct.pack(">iii", *destination))))
            saved = import_module("test-schematic-capture").read_nbt(path)
            ports = saved["data"]["create"]["train_postbox_ports"]["value"]["Ports"]
            assert len(ports) == 1 and ports[0]["Pos"] == list(destination), ports
            world.open()
            # The relocated synthetic entry is the only port in the Java oracle.
            world.command(f"/setblock {PORT[0]} {Y} {PORT[2]} minecraft:air")
        chest = world.command(f"/data get entity {train.ENTITY} {trip.CHEST_ITEMS}")
        assert PACKAGE not in chest, chest
        expected_cargo = [(0, "minecraft:paper", 64), (1, "minecraft:paper", 7),
                          (2, "minecraft:redstone", 64)]
        assert trip.chest_slots(chest) == expected_cargo, chest
        world.command("/attribute @s minecraft:gravity base set 0")
        conductor.set_held(world, world, "@s", conductor.SCHEDULE, components=trip.ITEM_CARGO_PROGRAM)
        conductor.click(world, world, "@s", 0)
        assert conductor.assigned(world) is not None
        world.command("/tp @s 512 120 512")
        start = world.clock()
        unloaded = False
        arrival = None
        for tick in range(23, 146):
            world.step_to(start + tick - 22)
            station_loaded = world.command(f"/execute if loaded {TERMINAL[0]} {Y} {TERMINAL[2]}") == "Test passed"
            port_loaded = world.command(f"/execute if loaded {destination[0]} {Y} {destination[2]}") == "Test passed"
            unloaded |= station_loaded and not port_loaded
            if args.dwell and tick == 110:
                world.command(f'/data merge block 20 112 4 {{Items:[{{Slot:0b,id:"{PACKAGE}",count:1,components:{{"create:package_address":"Later"}}}}]}}')
                world.command(f"/item replace block {PORT[0]} {Y} {PORT[2]} container.2 from block 20 112 4 container.0")
            if args.dwell and tick in (122, 123):
                box = world.command(f"/data get block {PORT[0]} {Y} {PORT[2]} Items")
                cargo = world.command(f"/data get entity {train.ENTITY} {trip.CHEST_ITEMS}")
                assert ("Later" in box, "Later" in cargo) == ((True, False) if tick == 122 else (False, True)), (tick, box, cargo)
                if tick == 123:
                    break
            state = world.command(f"/data get entity {train.ENTITY} CreateTrain.ArrivedStation")
            if arrival is None and f"{TERMINAL[0]}, {TERMINAL[1]}, {TERMINAL[2]}" in state:
                arrival = tick
                assert station_loaded, (tick, station_loaded)
                box_data = world.command(f"/data get block {destination[0]} {Y} {destination[2]}")
                if args.loaded:
                    assert port_loaded and "create:package_postbox" in box_data, box_data
                else:
                    assert unloaded and not port_loaded and "create:package_postbox" not in box_data, box_data
                if not args.dwell:
                    break
        assert arrival == first_arrival, (arrival, first_arrival, unloaded)
        chest = world.command(f"/data get entity {train.ENTITY} {trip.CHEST_ITEMS}")
        if args.loaded:
            live = world.command(f"/data get block {PORT[0]} {Y} {PORT[2]} Items")
            assert "Depot" in live and "Elsewhere" not in live and "Later" not in live, live
        world.stop()
        data = import_module("test-schematic-capture").read_nbt(path)
        ports = data["data"]["create"]["train_postbox_ports"]["value"]["Ports"]
        port = next(entry for entry in ports if entry["Pos"] == list(destination))
        items = port["OfflineBuffer"]["Items"]
        assert port["Primed"] == (0 if args.loaded else 1) and len(items) == 1 and items[0]["components"]["create:package_address"] == "Depot", port
        assert PACKAGE in chest and "Elsewhere" in chest, chest
        assert trip.chest_slots(chest) == expected_cargo + [(3, PACKAGE, 1)] + ([(4, PACKAGE, 1)] if args.dwell else []), chest
        print(f"Scheduled arrival at Java tick {arrival} imported outgoing mail from the {'loaded' if args.loaded else 'unloaded'} port." + (" Later mail transferred at tick 123." if args.dwell else "") + (" The targeted rail was replaced before the trip." if args.rebind else ""))



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--loaded", action="store_true")
    parser.add_argument("--dwell", action="store_true")
    parser.add_argument("--rebind", action="store_true")
    args = parser.parse_args()
    if (args.dwell or args.rebind) and not args.loaded:
        parser.error("--dwell and --rebind require --loaded")
    run(args)
