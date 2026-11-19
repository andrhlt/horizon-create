#!/usr/bin/env python3
"""Check an unseated player standing on and leaving a straight moving train."""
import argparse
import re
import time
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


def run(args):
    base.configure_positions()
    with fixture_world(args, "TrainStanding", train.STRUCTURE, render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.command("/attribute @s minecraft:gravity base set 0")
        world.command(f"/forceload add {train.X-21} {base.Z} {train.X+25} {base.Z}")
        train.setup(world, after_station=trip.place_stations, take_controls=False)
        conductor.set_held(world, world, "@s", conductor.SCHEDULE, components=trip.PROGRAM)
        conductor.click(world, world, "@s", 0)
        assert conductor.assigned(world) is not None
        world.command(f"/tp @s {train.X+3.5} {base.Y+3.0001001} {base.Z+0.5}")
        world.command("/attribute @s minecraft:gravity base set 0.08")
        x0, car0 = train.X + 3.5, carriage_x(world)
        world.command("/tick unfreeze")
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            time.sleep(0.1)
            player = world.call("state")["player"]
            x, y, z = player["position"]
            car = carriage_x(world)
            assert abs(y - (base.Y + 3.0001001)) < 0.2, (player, car)
            if abs(car - car0) > 0.7:
                assert abs((x - x0) - (car - car0)) < 0.3, (player, car, car0)
                break
        else:
            raise AssertionError("Train did not move in live mode")
        world.command("/attribute @s minecraft:movement_speed base set 0.1")
        world.command(f"/tp @s {x} {y} {z} 0 0")
        world.call("key", "w", "down")
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                time.sleep(0.1)
                player = world.call("state")["player"]
                if player["position"][2] > z + 0.8 and player["position"][1] < base.Y + 2.5:
                    break
            else:
                raise AssertionError(("Player did not walk off the moving deck", player))
        finally:
            world.call("key", "w", "up")
        print("Player stayed on the live moving carriage and fell after walking off its edge.")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    run(parser.parse_args())
