#!/usr/bin/env python3
"""Compare the first rendered freestanding door pose after a real reopen."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

pairs = import_module("test-world-paired-doors")
ENV = {**pairs.ENV, "HORIZON_CREATE_WORLD_DOOR_TRACE": "1"}
MATERIALS = ("brass_door", "copper_door")


def observe(view, material, minimum_tick):
    def visible_samples():
        samples = pairs.drawn_samples(view, material, 0)
        selected = {key: value for key, value in samples.items() if key[0] >= minimum_tick}
        return selected if {key[1] for key in selected} == {0, 1} else None

    return pairs.multiplayer.until("both reopened leaves to render", visible_samples)


def run(args):
    with (ROOT / "fixtures/world-door-fresh-animation-java.csv").open() as handle:
        endpoints = {row["material"]: float(row["progress"]) for row in csv.DictReader(handle)
                     if row["open"] == "true"}

    for material in MATERIALS:
        scenario = f"ColdWorldDoor{material}{'Lan' if args.lan else 'Solo'}"
        with fixture_world(args, scenario, render=True, pack=args.pack, env=ENV) as world:
            positions = pairs.place_pair(world, material, 8, 170, 8)
            observer_x = 10.5 if args.lan else 8.25
            world.command(f"/tp @s {observer_x} 170 10.5")
            world.call("look-at", 8.9, 171, 8.9)
            with ExitStack() as connected:
                actor = pairs.join(args, world, connected, material, ENV) if args.lan else world
                opened = world.clock()
                pairs.click(world, actor, positions[0], closing=False)
                frames = observe(world, material, opened)
                endpoint = endpoints[material]
                assert any(value[1] < endpoint for value in frames.values()), frames
            saved = world.clock()
            assert saved == opened, (saved, opened)
            world.restart()
            world.command(f"/tp @s {observer_x} 170 10.5")
            world.call("look-at", 8.9, 171, 8.9)
            frames = observe(world, material, saved)
            assert min(tick for tick, _ in frames) < opened + 7, frames
            assert set(frames.values()) == {(endpoint, endpoint)}, frames
            assert pairs.sample(world, positions, material) == ("1111", "0000", "0000")
            if args.lan:
                with ExitStack() as connected:
                    guest = pairs.join(args, world, connected, material, ENV)
                    world.command(f"/tp {pairs.GUEST} 8.25 170 10.5")
                    guest.call("look-at", 8.9, 171, 8.9)
                    frames = observe(guest, material, saved)
                    assert set(frames.values()) == {(endpoint, endpoint)}, frames
                    assert pairs.sample(guest, positions, material) == ("1111", "0000", "0000")
            print(f"{material}: first reopened pose is the complete Java open position.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())
