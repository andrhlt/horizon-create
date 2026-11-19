#!/usr/bin/env python3
"""Compare Honey and Chocolate in a horizontal stone channel against Java."""
import argparse
import csv
from pathlib import Path

from fixture_world import ROOT, fixture_world

CHANNELS = {"honey": 20, "chocolate": 24}


def run(args):
    with (ROOT / "fixtures/honey-chocolate-flow-java.csv").open(newline="") as stream:
        expected = list(csv.DictReader(stream))
    env = {"HORIZON_NO_AUDIO": "1"}
    with fixture_world(args, "HoneyChocolateFlow", pack=args.pack, env=env) as world:
        for z in CHANNELS.values():
            world.commands((
                f"/fill 8 169 {z - 1} 14 171 {z + 1} minecraft:air",
                f"/fill 9 169 {z} 13 169 {z} minecraft:stone",
                f"/fill 9 170 {z - 1} 13 170 {z - 1} minecraft:stone",
                f"/fill 9 170 {z + 1} 13 170 {z + 1} minecraft:stone",
                f"/setblock 8 170 {z} minecraft:stone",
            ))
        for fluid, z in CHANNELS.items():
            assert "Changed the block" in world.command(f"/setblock 9 170 {z} create:{fluid}")
        start = world.clock()
        actual = []
        expected = sorted(expected, key=lambda row: (int(row["tick"]), row["fluid"], int(row["x_offset"])))
        for tick in range(max(int(row["tick"]) for row in expected) + 1):
            if tick:
                world.step_to(start + tick)
            rows = [row for row in expected if int(row["tick"]) == tick]
            if not rows:
                continue
            blocks = world.call("script", script="".join(
                f"block {9 + int(row['x_offset'])} 170 {CHANNELS[row['fluid']]}\n" for row in rows))
            for row, block in zip(rows, blocks, strict=True):
                want_state = row["block_id"] + row["block_state"].split("}", 1)[1]
                if (block["block"], block["state"]) != (row["block_id"], want_state):
                    actual.append((row["fluid"], tick, row["x_offset"], want_state, block["state"]))
        assert world.clock() == start + tick
    assert not actual, actual[:10]
    print(f"Honey and Chocolate matched all {len(expected)} Java channel samples.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
