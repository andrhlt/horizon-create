#!/usr/bin/env python3
"""Compare a cold Horizon conveyor replay with a pinned Java server restart."""

import argparse
import csv
import importlib
from pathlib import Path
from struct import pack

from fixture_world import ROOT, fixture_world


chain = importlib.import_module("test-chain-conveyor-packages")
player = importlib.import_module("test-chain-conveyor-player")
A = (8, 102, -10)


def run(args):
    with (ROOT / "fixtures" / f"chain-conveyor-restart-{args.scenario}-java.csv").open() as stream:
        expected = list(csv.DictReader(stream))
    edge = chain.WHEELS[args.scenario]
    b = tuple(x + delta for x, delta in zip(A, edge))
    motor = (8, 101, -10)
    saved = expected[0]
    with fixture_world(args, f"ChainRestart-{args.scenario}", pack=args.pack) as world:
        chain.setup(world, A, b, motor, (17, 100, -10), edge, True)
        if args.scenario == "rising_reversal":
            chain.merge(world, motor, "{ScrollValue:-128}")
            world.step_to(world.clock() + 1)
        cargo = chain.stack("Lab-In", "paper", 3)
        chain.merge(world, A, f"{{Packages:[{{Item:{cargo},Position:{saved['position']}f,"
                              f"Connection:{chain.emit_vector(edge)}}}]}}")
        clock = world.clock()
        compare(world, b, saved)

        world.call("save")
        world.env["HORIZON_STILL"] = "1"
        world.restart()
        assert world.clock() == clock
        # The original Java server's first observation is its first loaded
        # tick. Its blocks have deserialized but its conveyor states have not
        # advanced yet. Match that state while the reopened Horizon is frozen.
        for sample in expected[1:]:
            tick = int(sample["tick"])
            if tick:
                world.step_to(clock + tick)
            compare(world, b, sample)
    print(f"{args.scenario}: saved state and 15 post-restart Java package states")


def compare(world, b, sample):
    actual, packages = [], []
    for at in (A, b):
        reply = world.command(f"/data get block {chain.coords(at)}").partition("block data: ")[2]
        actual.append((float(chain.scalar(reply, "Speed")), chain.scalar(reply, "Reversed") != "0"))
        tags = player.get(world, at, "Packages")
        for entry in chain.snbt.top_level_entries(tags):
            assert chain.payload(entry) == "Lab-In:paper:3", entry
            packages.append(("A" if at == A else "B",
                             "span" if "Connection:" in entry else "loop",
                             pack("f", float(chain.scalar(entry, "Position")))))
    speeds = [(float(sample[f"rpm_{wheel}"]), sample[f"reverse_{wheel}"] == "true") for wheel in ("a", "b")]
    cargo = [(sample["owner"], sample["path"], pack("f", float(sample["position"])))]
    assert actual == speeds and packages == cargo, (sample, actual, packages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--scenario", choices=chain.WHEELS, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
