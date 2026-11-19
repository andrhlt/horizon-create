#!/usr/bin/env python3
"""Run the original dirt and grass path pressing recipes on real Depots."""
import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

pressing = import_module("test-depot-pressing")
INPUTS = ("dirt", "coarse_dirt", "rooted_dirt", "mycelium", "podzol", "grass_block", "sand")


def run(args):
    env = {"HORIZON_NO_AUDIO": "1"}
    with fixture_world(args, "DirtPathPressing", pack=args.pack, env=env) as world:
        for index in range(len(INPUTS)):
            z = 6 + 3 * index
            world.commands((
                f"/setblock 4 106 {z} create:creative_motor[facing=east]{{ScrollValue:128}}",
                f"/setblock 5 106 {z} create:mechanical_press[facing=east]",
                f"/setblock 5 104 {z} create:depot",
            ))
        world.step_to(world.clock() + 1)
        for index, item in enumerate(INPUTS):
            assign = world.command(f"/item replace block 5 104 {6 + 3 * index} container.0 with minecraft:{item}")
            assert "Replaced" in assign, assign
        tick = world.clock()
        for offset in range(1, 34):
            world.step_to(tick + offset)
        for index, item in enumerate(INPUTS):
            depot = world.command(f"/data get block 5 104 {6 + 3 * index}")
            counts = pressing.item_counts(depot, "minecraft:" + item, "minecraft:dirt_path")
            expected = (1, 0, 0) if item == "sand" else (0, 1, 0)
            assert counts == expected, (item, counts, depot)
    print("Six original terrain variants pressed into Dirt Path. Sand remained untouched.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
