#!/usr/bin/env python3
"""Measure the original comparator and wire at the dock of a parked train.

Apply java-scheduled-train-fluid-port-trace.patch and
java-portable-interface-readout-and-wrench-trace.patch to the pinned Create
checkout. Run ./gradlew -PparityPortableComparator=fluid runGameTestServer
and repeat with =item. Both original flavors emit CREATE_PORT_COMPARATOR
records for two lock/unlock cycles with identical measured timing.
"""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

moving = import_module("test-train-moving-port-render")
wrench = import_module("test-wrench")
multiplayer = import_module("test-multiplayer")
ROOT = Path(__file__).resolve().parent.parent
PORT = moving.schedule.PORTABLE_FLUID_POS
METER = (PORT[0] - 1, PORT[1], PORT[2])
WIRE = (PORT[0] - 2, PORT[1], PORT[2])
POWER = moving.POWER
coords = moving.schedule.coordinates


def setup(world, kind):
    moving.setup(world, kind)
    world.commands((
        f"/setblock {coords((METER[0], METER[1] - 1, METER[2]))} minecraft:smooth_stone",
        f"/setblock {coords((WIRE[0], WIRE[1] - 1, WIRE[2]))} minecraft:smooth_stone",
        f"/setblock {coords(WIRE)} minecraft:redstone_wire",
        f"/setblock {coords(METER)} minecraft:comparator[facing=east]",
    ))


def exercise(world, reference, guest=None):
    differences = []
    observed = []
    for row in reference:
        tick = int(row["tick"])
        world.step_to(world.clock() + 1)
        replies = world.commands((
            f"/data get block {coords(PORT)} Timer",
            f"/data get block {coords(METER)} OutputSignal",
        ))
        timer, meter = (int(reply.split()[-1]) if "block data:" in reply else 0 for reply in replies)
        _, wire = wrench.state(world.call("block", *WIRE)["state"])
        actual = timer, meter, int(wire.get("power", -1))
        expected = tuple(int(row[field]) for field in ("timer", "meter", "wire"))
        observed.append((tick, *actual))
        if actual != expected:
            differences.append((tick, actual, expected))
        if guest and tick in (35, 55, 64, 74):
            multiplayer.until(f"portable comparator dust at {tick}", lambda: int(
                wrench.state(guest.call("block", *WIRE)["state"])[1].get("power", -1)
            ) == expected[-1])
        if tick in (30, 45, 60, 65):
            value = "air" if tick in (30, 60) else "redstone_block"
            world.command(f"/setblock {POWER} minecraft:{value}")
    if differences:
        print("Observed parked comparator trace:", observed)
        raise RuntimeError(f"{len(differences)} original comparator mismatches: {differences[:30]}.")
    print(f"Both power cycles matched all {len(reference)} Java timer, comparator and wire samples.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--item", action="store_true")
    parser.add_argument("--multiplayer", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    variant = "item" if args.item else "fluid"
    kind = "portable_storage_interface" if args.item else "portable_fluid_interface"
    label = f"portable-{variant}-comparator"
    if args.multiplayer:
        label += "-lan"
    with (ROOT / "fixtures/portable_comparator-java.csv").open() as f:
        reference = list(csv.DictReader(f))
    with fixture_world(args, label, moving.train.STRUCTURE, render=True, pack=args.pack) as world:
        moving.train.setup(world, after_station=lambda world: setup(world, kind), take_controls=False)
        if not args.multiplayer:
            exercise(world, reference)
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        name = "PortAnalogGuest"
        with TemporaryDirectory(prefix="hc-pca-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", name, render=True,
            scenario=label, pack=args.pack,
        ) as guest:
            multiplayer.until("a guest at the comparator", lambda: any(
                player["name"] == name and player["placed"] for player in world.call("lan", "status")["guests"]
            ))
            world.commands((f"/gamemode spectator {name}", f"/tp {name} 8.5 118 -5.7"))
            multiplayer.until("the original comparator and wire to load", lambda: (
                guest.call("block", *METER)["block"] == "minecraft:comparator"
                and guest.call("block", *WIRE)["block"] == "minecraft:redstone_wire"
            ))
            exercise(world, reference, guest=guest)


if __name__ == "__main__":
    main()
