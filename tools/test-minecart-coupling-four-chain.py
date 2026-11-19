#!/usr/bin/env python3
"""Compare a four-cart chain on straight rails with pinned Java."""
import argparse
import csv
import importlib.util
from pathlib import Path

from fixture_world import fixture_world

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("chain_slope", Path(__file__).with_name("test-minecart-coupling-chain-slope.py"))
chain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chain)
FIELDS = [f"{tag}_{value}" for tag in ("a", "b", "c", "d", "base") for value in ("x", "y", "vx", "vy")]


def run(args):
    fixture = "minecart-coupling-four-reverse-java.csv" if args.reverse else "minecart-coupling-four-curve-java.csv" if args.curve else "minecart-coupling-four-chain-java.csv"
    with (ROOT / "fixtures" / fixture).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not 1 <= args.ticks <= len(rows):
        raise ValueError("invalid tick count")
    rows = rows[:args.ticks]
    with fixture_world(args, "MinecartFourChain", pack=args.pack, render=not args.lan) as world:
        commands = [
            "/fill 4 169 20 22 169 42 minecraft:stone",
            "/fill 4 170 20 22 173 42 minecraft:air",
            "/fill 4 170 24 22 170 24 minecraft:rail[shape=east_west]",
            "/fill 4 170 32 22 170 32 minecraft:rail[shape=east_west]",
            '/summon minecraft:minecart 5.5 170.0625 24.5 {UUID:[I;0,0,0,1],Motion:[0.1d,0d,0d],Tags:["chain_a"]}',
            '/summon minecraft:minecart 8.5 170.0625 24.5 {UUID:[I;0,0,0,2],Tags:["chain_b"]}',
            '/summon minecraft:minecart 11.5 170.0625 24.5 {UUID:[I;0,0,0,3],Tags:["chain_c"]}',
            '/summon minecraft:minecart 14.5 170.0625 24.5 {UUID:[I;0,0,0,4],Tags:["chain_d"]}',
            '/summon minecraft:minecart 5.5 170.0625 32.5 {UUID:[I;0,0,0,5],Motion:[0.1d,0d,0d],Tags:["chain_base"]}',
        ]
        if args.curve:
            commands[2:4] = [
                "/fill 4 170 24 13 170 24 minecraft:rail[shape=east_west]",
                "/fill 14 170 25 14 170 32 minecraft:rail[shape=north_south]",
                "/setblock 14 170 24 minecraft:rail[shape=south_west]",
                "/fill 4 170 32 13 170 32 minecraft:rail[shape=east_west]",
                "/fill 14 170 33 14 170 40 minecraft:rail[shape=north_south]",
                "/setblock 14 170 32 minecraft:rail[shape=south_west]",
            ]
            commands = [command.replace(" 5.5 170.0625", " 5.25 170.0625").replace(" 8.5 170.0625", " 8.25 170.0625").replace(" 11.5 170.0625", " 11.25 170.0625").replace(" 14.5 170.0625 24.5", " 14.25 170.0625 24.75") for command in commands]
        world.commands(commands)
        shape = "south_west" if args.curve else "east_west"
        for z in (24, 32):
            if f"shape={shape}" not in world.call("block", 14, 170, z)["state"]:
                raise RuntimeError("wrong straight rail")
        for i, tag in enumerate(("chain_a", "chain_b", "chain_c", "chain_d", "chain_base"), 1):
            uuid = world.command(f"/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID")
            if f"[I; 0, 0, 0, {i}]" not in uuid:
                raise RuntimeError(f"Wrong UUID: {uuid}")
        positions = ((5.5, 24.5), (8.5, 24.5), (8.5, 24.5), (11.5, 24.5), (11.5, 24.5), (14.5, 24.5))
        if args.curve: positions = ((5.25, 24.5), (8.25, 24.5), (8.25, 24.5), (11.25, 24.5), (11.25, 24.5), (14.25, 24.75))
        if args.reverse: positions = ((14.5, 24.5), (11.5, 24.5), (11.5, 24.5), (8.5, 24.5), (8.5, 24.5), (5.5, 24.5))
        with chain.chain_curve.player_chain(world, args, positions, count=4):
            links = world.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]')
            if "Count: 3" not in links:
                raise RuntimeError(f"Missing links: {links}")
            for row in rows:
                sampler = chain.chain_curve.sample if args.curve else chain.sample
                actual = sum((sampler(world, tag) for tag in ("chain_a", "chain_b", "chain_c", "chain_d", "chain_base")), [])
                fields = [f"{tag}_{value}" for tag in ("a", "b", "c", "d", "base") for value in ("x", "z", "vx", "vz")] if args.curve else FIELDS
                target = [float(row[key]) for key in fields]
                start = 16 if args.base_only else 0
                end = 16 if args.chain_only else len(FIELDS)
                if any(abs(a - b) > 0.00001 for a, b in zip(actual[start:end], target[start:end])):
                    raise RuntimeError(f"Tick {row['tick']} differs from Java: {actual} vs {target}")
                if int(row["tick"]) != len(rows) - 1:
                    world.step_to(world.clock() + 1)
    scope = "standalone" if args.base_only else "chain" if args.chain_only else "chain and standalone"
    print(f"Matched {len(rows)} four-cart Java ticks for {scope}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--base-only", action="store_true")
    group.add_argument("--chain-only", action="store_true")
    parser.add_argument("--lan", action="store_true")
    direction = parser.add_mutually_exclusive_group()
    direction.add_argument("--curve", action="store_true")
    direction.add_argument("--reverse", action="store_true")
    parser.add_argument("--ticks", type=int, default=81)
    run(parser.parse_args())
