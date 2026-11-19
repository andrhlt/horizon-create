#!/usr/bin/env python3
"""Compare naturally generated Create and vanilla blocks in the same seed and chunks."""

import argparse
from collections import Counter
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")

ORES = frozenset(("create:zinc_ore", "create:deepslate_zinc_ore",
                  "minecraft:gold_ore", "minecraft:deepslate_gold_ore"))


NETHER_ORES = {"minecraft:nether_gold_ore", "minecraft:nether_quartz_ore", "minecraft:ancient_debris"}
STRIATED = {f"create:{name}" for name in ("asurine", "crimsite", "limestone", "ochrum", "scoria", "scorchia", "veridium")}


def scan(control, chunks, blocks, nether, halo, force_before_view):
    edge = chunks * 16 - 1
    midpoint = edge / 2
    loaded = f"{-halo * 16} {-halo * 16} {edge + halo * 16} {edge + halo * 16}"
    bottom = 0 if nether else -64
    prefix = "execute in minecraft:the_nether run " if nether else ""
    control.command(f"/{prefix}forceload add {loaded}")
    if force_before_view:
        queries = [
            f"/{prefix}execute if block {x * 16} {bottom} {z * 16} minecraft:bedrock"
            for x in range(-halo, chunks + halo) for z in range(-halo, chunks + halo)
        ]
        multiplayer.until("each forced terrain chunk to load before teleport",
                          lambda: all(reply.startswith("Test passed") for reply in control.commands(queries)),
                          seconds=90)
    if nether:
        control.command(f"/{prefix}tp @s {midpoint} 132 {midpoint}")
    else:
        control.call("tp", midpoint, 140, midpoint)
    ranges = ((0, 63), (64, 127)) if nether else ((-64, 8), (9, 80))
    control.call("wait-ready")
    control.call("wait", 10)
    rows = []
    for cx in range(chunks):
        for cz in range(chunks):
            origin = control.call("block", cx * 16, bottom, cz * 16)
            if not origin["loaded"] or origin["block"] != "minecraft:bedrock":
                raise RuntimeError(f"Missing generated chunk ({cx}, {cz}): {origin}")
            for low, high in ranges:
                result = control.call("blocks", cx * 16, low, cz * 16, cx * 16 + 15, high, cz * 16 + 15)
                rows.extend((x, y, z, block) for x, y, z, block in result["blocks"] if block in blocks)
    return sorted(rows)


def count(rows):
    return dict(sorted(Counter(block for *_, block in rows).items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--seed", type=int, default=810102)
    parser.add_argument("--chunks", type=int, default=2)
    parser.add_argument("--halo", type=int, default=0, help="force-load surrounding chunks before comparing")
    parser.add_argument("--include-striated", action="store_true")
    parser.add_argument("--force-before-view", action="store_true")
    parser.add_argument("--nether", action="store_true")
    parser.add_argument("--reopen", action="store_true")
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blocks = NETHER_ORES if args.nether else ORES
    if args.include_striated or args.nether:
        blocks = blocks | STRIATED
    scenario = "Nether-striated-worldgen" if args.nether else "Zinc-worldgen"
    with fixture_world(args, scenario, pack=args.pack, terrain_seed=args.seed) as world:
        actual = scan(world, args.chunks, blocks, args.nether, args.halo, args.force_before_view)
        if args.reopen:
            world.restart()
            reopened = scan(world, args.chunks, blocks, args.nether, args.halo, args.force_before_view)
            if reopened != actual:
                raise RuntimeError("The sampled generated blocks changed after saving and reopening.")
    with args.output.open("w", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(("x", "y", "z", "block"))
        writer.writerows(actual)
    print(f"Horizon seed {args.seed} counts: {count(actual)}")
    if args.reference is not None:
        with args.reference.open(newline="") as source:
            wanted = sorted((int(row["x"]), int(row["y"]), int(row["z"]), row["block"])
                            for row in csv.DictReader(source))
        if actual != wanted:
            horizon_only = set(actual) - set(wanted)
            java_only = set(wanted) - set(actual)
            raise RuntimeError(f"Java counts: {count(wanted)}. Horizon-only: {count(horizon_only)}, Java-only: {count(java_only)}.")
        print(f"All {len(actual)} sampled block positions and materials match Java.")


if __name__ == "__main__":
    main()
