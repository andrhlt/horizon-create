#!/usr/bin/env python3
"""Compare a three-cart chain entering an ascending-east rail with Java."""
import argparse, csv, re
import importlib.util
from pathlib import Path
from fixture_world import fixture_world
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("chain_curve", Path(__file__).with_name("test-minecart-coupling-chain-curve.py"))
chain_curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chain_curve)
FIELDS = [f"{tag}_{value}" for tag in ("a", "b", "c", "base") for value in ("x", "y", "vx", "vy")]

def sample(world, tag, south=False):
    data = world.command(f"/data get entity @e[type=minecraft:minecart,tag={tag},limit=1]")
    result = []
    for key in ("Pos", "Motion"):
        match = re.search(key + r": \[([-0-9.eE]+)d, ([-0-9.eE]+)d, ([-0-9.eE]+)d\]", data)
        if not match: raise RuntimeError(f"Missing {key}: {data}")
        result.extend((float(match.group(3 if south else 1)), float(match.group(2))))
    return result

def run(args):
    ns = args.south or args.north
    hard = args.hard_flat or args.hard_expand
    fixture = "minecart-coupling-chain-expand-java.csv" if args.hard_expand else "minecart-coupling-chain-hard-java.csv" if args.hard_flat else "minecart-coupling-chain-slope-north-java.csv" if args.north else "minecart-coupling-chain-slope-south-java.csv" if args.south else "minecart-coupling-chain-slope-west-java.csv" if args.west else "minecart-coupling-chain-slope-java.csv"
    with (ROOT / "fixtures" / fixture).open(newline="") as f: rows = list(csv.DictReader(f))
    with fixture_world(args,"MinecartChainSlope",pack=args.pack,render=not args.lan) as world:
        commands = ["/fill 4 169 20 22 169 42 minecraft:stone", "/fill 4 170 20 22 173 42 minecraft:air"]
        for z in (24,32):
            if hard:
                commands += [f"/fill 4 170 {z} 22 170 {z} minecraft:rail[shape=east_west]"]
            elif args.north:
                commands += [f"/fill {z} 170 4 {z} 170 13 minecraft:stone", f"/fill {z} 170 15 {z} 170 22 minecraft:rail[shape=north_south]", f"/fill {z} 171 4 {z} 171 13 minecraft:rail[shape=north_south]", f"/setblock {z} 170 14 minecraft:rail[shape=ascending_north]"]
            elif args.south:
                commands += [f"/fill {z} 170 13 {z} 170 22 minecraft:stone", f"/fill {z} 170 4 {z} 170 11 minecraft:rail[shape=north_south]", f"/fill {z} 171 13 {z} 171 22 minecraft:rail[shape=north_south]", f"/setblock {z} 170 12 minecraft:rail[shape=ascending_south]"]
            elif args.west:
                commands += [f"/fill 4 170 {z} 13 170 {z} minecraft:stone", f"/fill 15 170 {z} 22 170 {z} minecraft:rail[shape=east_west]", f"/fill 4 171 {z} 13 171 {z} minecraft:rail[shape=east_west]", f"/setblock 14 170 {z} minecraft:rail[shape=ascending_west]"]
            else:
                commands += [f"/fill 13 170 {z} 22 170 {z} minecraft:stone", f"/fill 4 170 {z} 11 170 {z} minecraft:rail[shape=east_west]", f"/fill 13 171 {z} 22 171 {z} minecraft:rail[shape=east_west]", f"/setblock 12 170 {z} minecraft:rail[shape=ascending_east]"]
        commands += [
            '/summon minecraft:minecart 5.5 170.0625 24.5 {UUID:[I;0,0,0,1],Motion:[0.1d,0d,0d],Tags:["chain_a"]}',
            '/summon minecraft:minecart 8.5 170.0625 24.5 {UUID:[I;0,0,0,2],Tags:["chain_b"]}',
            '/summon minecraft:minecart 11.5 170.0625 24.5 {UUID:[I;0,0,0,3],Tags:["chain_c"]}',
            '/summon minecraft:minecart 11.5 170.0625 32.5 {UUID:[I;0,0,0,4],Motion:[0.1d,0d,0d],Tags:["chain_base"]}',
            ]
        if hard:
            commands[-4:] = [
                '/summon minecraft:minecart 8.5 170.0625 24.5 {UUID:[I;0,0,0,1],Motion:[0.3d,0d,0d],Tags:["chain_a"]}',
                '/summon minecraft:minecart 11.5 170.0625 24.5 {UUID:[I;0,0,0,2],Tags:["chain_b"]}',
                '/summon minecraft:minecart 14.5 170.0625 24.5 {UUID:[I;0,0,0,3],Tags:["chain_c"]}',
                '/summon minecraft:minecart 8.5 170.0625 32.5 {UUID:[I;0,0,0,4],Motion:[0.3d,0d,0d],Tags:["chain_base"]}']
        if args.hard_expand:
            commands[-4] = commands[-4].replace('Motion:[0.3d,0d,0d],', '')
            commands[-2] = commands[-2].replace('Tags:', 'Motion:[0.3d,0d,0d],Tags:')
        if args.west:
            commands = [c.replace(" 5.5 170.0625", " 21.5 170.0625").replace(" 8.5 170.0625", " 18.5 170.0625").replace(" 11.5 170.0625", " 15.5 170.0625").replace("Motion:[0.1d", "Motion:[-0.1d") for c in commands]
        if ns:
            commands[0] = "/fill 20 169 4 42 169 22 minecraft:stone"
            commands[1] = "/fill 20 170 4 42 173 22 minecraft:air"
            commands[-4:] = [
                '/summon minecraft:minecart 24.5 170.0625 5.5 {UUID:[I;0,0,0,1],Motion:[0d,0d,0.1d],Tags:["chain_a"]}',
                '/summon minecraft:minecart 24.5 170.0625 8.5 {UUID:[I;0,0,0,2],Tags:["chain_b"]}',
                '/summon minecraft:minecart 24.5 170.0625 11.5 {UUID:[I;0,0,0,3],Tags:["chain_c"]}',
                '/summon minecraft:minecart 32.5 170.0625 11.5 {UUID:[I;0,0,0,4],Motion:[0d,0d,0.1d],Tags:["chain_base"]}']
        if args.north:
            commands[-4:] = [c.replace(" 5.5 {", " 21.5 {").replace(" 8.5 {", " 18.5 {").replace(" 11.5 {", " 15.5 {").replace("0d,0d,0.1d", "0d,0d,-0.1d") for c in commands[-4:]]
        world.commands(commands)
        rails = ((15,170,"east_west"),(14,170,"ascending_west"),(13,171,"east_west")) if args.west else ((11,170,"east_west"),(12,170,"ascending_east"),(13,171,"east_west"))
        if hard: rails = ((8,170,"east_west"),(11,170,"east_west"),(14,170,"east_west"))
        if args.south: rails = ((11,170,"north_south"),(12,170,"ascending_south"),(13,171,"north_south"))
        if args.north: rails = ((15,170,"north_south"),(14,170,"ascending_north"),(13,171,"north_south"))
        for z in (24,32):
            for x,y,shape in rails:
                block=world.call("block",z,y,x) if ns else world.call("block",x,y,z)
                if f"shape={shape}" not in block["state"]: raise RuntimeError(f"Wrong rail: {block}")
        for i,tag in enumerate(("chain_a","chain_b","chain_c","chain_base"),1):
            uuid=world.command(f"/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID")
            if f"[I; 0, 0, 0, {i}]" not in uuid: raise RuntimeError(f"Wrong UUID: {uuid}")
        positions = ((21.5,24.5),(18.5,24.5),(18.5,24.5),(15.5,24.5)) if args.west else ((5.5,24.5),(8.5,24.5),(8.5,24.5),(11.5,24.5))
        if hard: positions = ((8.5,24.5),(11.5,24.5),(11.5,24.5),(14.5,24.5))
        if args.south: positions = ((24.5,5.5),(24.5,8.5),(24.5,8.5),(24.5,11.5))
        if args.north: positions = ((24.5,21.5),(24.5,18.5),(24.5,18.5),(24.5,15.5))
        with chain_curve.player_chain(world,args,positions,side=ns):
            links=world.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]')
            if "Count: 2" not in links: raise RuntimeError(f"Missing links: {links}")
            for row in rows:
                actual=sum((sample(world,tag,ns) for tag in ("chain_a","chain_b","chain_c","chain_base")),[])
                fields = [f"{tag}_{v}" for tag in ("a","b","c","base") for v in ("z","y","vz","vy")] if ns else FIELDS
                target=[float(row[k]) for k in fields];start=12 if args.base_only else 0
                if any(abs(a-b)>0.00001 for a,b in zip(actual[start:],target[start:])): raise RuntimeError(f"Tick {row['tick']} differs from Java: {actual} vs {target}")
                if int(row["tick"]) != len(rows)-1: world.step_to(world.clock()+1)
    print(f"Matched {len(rows)} Java chain-slope ticks for {'standalone' if args.base_only else 'chain and standalone'}.")

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("ctl","client","resources"):parser.add_argument(name,type=lambda value:Path(value).resolve(strict=True))
    parser.add_argument("--pack",type=lambda value:Path(value).resolve(strict=True))
    parser.add_argument("--base-only",action="store_true")
    parser.add_argument("--lan",action="store_true")
    direction=parser.add_mutually_exclusive_group()
    direction.add_argument("--west",action="store_true")
    direction.add_argument("--south",action="store_true")
    direction.add_argument("--north",action="store_true")
    direction.add_argument("--hard-flat",action="store_true")
    direction.add_argument("--hard-expand",action="store_true")
    run(parser.parse_args())
