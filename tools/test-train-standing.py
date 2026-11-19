#!/usr/bin/env python3
"""Check an unseated player standing on and leaving a straight moving train."""
import argparse
import re
import struct
import zlib
from importlib import import_module
from pathlib import Path
from fixture_world import fixture_world

base = import_module("test-train-postbox-import")
trip, train, conductor = base.trip, base.train, base.conductor
NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?"


def carriage_x(world):
    reply = world.command(f"/data get entity {train.ENTITY} Pos")
    match = re.search(r"entity data: \[\s*(" + NUMBER + r")[dDfF]?", reply)
    assert match, reply
    return float(match.group(1))


def strip_collision_fields(directory):
    # Older trains have the same captured blocks but no collision long arrays.
    marker = b"\x0c\x00\x17CreateElevatorCollision"
    removed = 0
    for path in directory.glob("*.mca"):
        region = bytearray(path.read_bytes())
        for index in range(1024):
            entry = region[index * 4:index * 4 + 4]
            offset = int.from_bytes(entry[:3], "big") * 4096
            if not offset:
                continue
            size = struct.unpack_from(">I", region, offset)[0]
            if region[offset + 4] != 2:
                continue
            data = zlib.decompress(region[offset + 5:offset + 4 + size])
            old = data
            while (at := data.find(marker)) >= 0:
                length = struct.unpack_from(">I", data, at + len(marker))[0]
                end = at + len(marker) + 4 + length * 8
                assert end <= len(data)
                data = data[:at] + data[end:]
                removed += 1
            if data != old:
                encoded = zlib.compress(data)
                assert len(encoded) + 5 <= entry[3] * 4096
                struct.pack_into(">I", region, offset, len(encoded) + 1)
                region[offset + 5:offset + 5 + len(encoded)] = encoded
        path.write_bytes(region)
    assert removed > 0


def run(args):
    base.configure_positions()
    with fixture_world(args, "TrainStanding", train.STRUCTURE, render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.command("/attribute @s minecraft:gravity base set 0")
        world.command(f"/forceload add {train.X-21} {base.Z} {train.X+25} {base.Z}")
        train.setup(world, after_station=trip.place_stations, take_controls=False)
        if args.legacy_snapshot:
            world.stop()
            game = Path(world._launch[world._launch.index("--game-dir") + 1])
            strip_collision_fields(game / "saves/TrainStanding/dimensions/minecraft/overworld/entities")
            world.open()
            saved = world.command(f"/data get entity {train.ENTITY} CreateTrain.Blocks")
            assert "CreateElevatorCollision" not in saved, saved
        conductor.set_held(world, world, "@s", conductor.SCHEDULE, components=trip.PROGRAM)
        conductor.click(world, world, "@s", 0)
        assert conductor.assigned(world) is not None
        world.command(f"/tp @s {train.X+3.5} {base.Y+3.0001001} {base.Z+0.5}")
        world.command("/attribute @s minecraft:gravity base set 0.08")
        start = world.clock()
        x0, car0 = train.X + 3.5, carriage_x(world)
        for tick in range(1, 31):
            world.step_to(start + tick)
            player = world.call("state")["player"]
            x, y, z = player["position"]
            car = carriage_x(world)
            assert abs(y - (base.Y + 3.0001001)) < 0.1, (tick, player, car)
            assert abs((x - x0) - (car - car0)) < 0.2, (tick, player, car)
        assert abs(car - car0) > 0.5, (car, car0)
        # Leave the deck laterally and verify that support does not extend to air.
        world.command(f"/tp @s {x} {y} {base.Z+3.5}")
        for tick in range(31, 37):
            world.step_to(start + tick)
        player = world.call("state")["player"]
        assert player["position"][1] < base.Y + 2.5, player
        print("An unseated player remained on the moving deck, then fell after leaving it.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--legacy-snapshot", action="store_true")
    run(parser.parse_args())
