#!/usr/bin/env python3
"""Compare a three-cart chain crossing a rail end with pinned Java."""
import argparse
import csv
import importlib.util
from pathlib import Path

from fixture_world import fixture_world

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("chain_slope", Path(__file__).with_name("test-minecart-coupling-chain-slope.py"))
chain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chain)
FIELDS = [f"{tag}_{value}" for tag in ("a", "b", "c", "base") for value in ("x", "y", "vx", "vy")]


def run(args):
    fixture = "minecart-coupling-chain-bothfree-java.csv" if args.both_free else "minecart-coupling-chain-offrail-java.csv"
    with (ROOT / "fixtures" / fixture).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not 1 <= args.ticks <= len(rows):
        raise ValueError("invalid tick count")
    rows = rows[:args.ticks]
    with fixture_world(args, "MinecartChainOffRail", pack=args.pack, render=not args.lan) as world:
        commands = [
            "/fill 4 169 20 22 169 42 minecraft:stone",
            "/fill 4 170 20 22 173 42 minecraft:air",
            "/fill 4 170 24 12 170 24 minecraft:rail[shape=east_west]",
            "/fill 4 170 32 12 170 32 minecraft:rail[shape=east_west]",
            '/summon minecraft:minecart 8.5 170.0625 24.5 {UUID:[I;0,0,0,1],Motion:[0.3d,0d,0d],Tags:["chain_a"]}',
            '/summon minecraft:minecart 11.5 170.0625 24.5 {UUID:[I;0,0,0,2],Motion:[0.3d,0d,0d],Tags:["chain_b"]}',
            '/summon minecraft:minecart 14.5 170.0625 24.5 {UUID:[I;0,0,0,3],Motion:[0.3d,0d,0d],Tags:["chain_c"]}',
            '/summon minecraft:minecart 14.5 170.0625 32.5 {UUID:[I;0,0,0,4],Motion:[0.3d,0d,0d],Tags:["chain_base"]}',
        ]
        if args.both_free:
            commands = [command.replace(" 8.5 170.0625", " 9.5 170.0625").replace(" 11.5 170.0625", " 12.5 170.0625").replace(" 14.5 170.0625", " 15.5 170.0625") for command in commands]
        world.commands(commands)
        for z in (24, 32):
            if "shape=east_west" not in world.call("block", 12, 170, z)["state"]:
                raise RuntimeError("last rail wrong")
            if "minecraft:air" not in world.call("block", 13, 170, z)["state"]:
                raise RuntimeError("rail continues")
        for i, tag in enumerate(("chain_a", "chain_b", "chain_c", "chain_base"), 1):
            uuid = world.command(f"/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID")
            if f"[I; 0, 0, 0, {i}]" not in uuid:
                raise RuntimeError(f"Wrong UUID: {uuid}")
        positions = ((9.5, 24.5), (12.5, 24.5), (12.5, 24.5), (15.5, 24.5)) if args.both_free else ((8.5, 24.5), (11.5, 24.5), (11.5, 24.5), (14.5, 24.5))
        with chain.chain_curve.player_chain(world, args, positions):
            links = world.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]')
            if "Count: 2" not in links:
                raise RuntimeError(f"Missing links: {links}")
            for row in rows:
                actual = sum((chain.sample(world, tag) for tag in ("chain_a", "chain_b", "chain_c", "chain_base")), [])
                target = [float(row[key]) for key in FIELDS]
                start = 12 if args.base_only else 0
                end = 12 if args.chain_only else len(FIELDS)
                if any(abs(a - b) > 0.00001 for a, b in zip(actual[start:end], target[start:end])):
                    raise RuntimeError(f"Tick {row['tick']} differs from Java: {actual} vs {target}")
                if int(row["tick"]) != len(rows) - 1:
                    world.step_to(world.clock() + 1)
    scope = "standalone" if args.base_only else "chain" if args.chain_only else "chain and standalone"
    print(f"Matched {len(rows)} rail-end chain Java ticks for {scope}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--base-only", action="store_true")
    group.add_argument("--chain-only", action="store_true")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--both-free", action="store_true")
    parser.add_argument("--ticks", type=int, default=81)
    run(parser.parse_args())
