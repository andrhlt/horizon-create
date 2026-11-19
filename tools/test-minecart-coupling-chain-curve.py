#!/usr/bin/env python3
"""Compare three player-coupled carts across straight and curved rails with Java."""
import argparse, csv, re
from contextlib import contextmanager
import importlib.util
from tempfile import TemporaryDirectory
from pathlib import Path
from fixture_world import fixture_world
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("multiplayer", Path(__file__).with_name("test-multiplayer.py"))
multiplayer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multiplayer)
GUEST = "CouplingGuest"
FIELDS = [f"{tag}_{value}" for tag in ("a", "b", "c", "base") for value in ("x", "z", "vx", "vz")]

def sample(world, tag):
    data = world.command(f"/data get entity @e[type=minecraft:minecart,tag={tag},limit=1]")
    result = []
    for key in ("Pos", "Motion"):
        match = re.search(key + r": \[([-0-9.eE]+)d, ([-0-9.eE]+)d, ([-0-9.eE]+)d\]", data)
        if not match: raise RuntimeError(f"Missing {key}: {data}")
        result.extend((float(match.group(1)), float(match.group(3))))
    return result

@contextmanager
def player_chain(world, args, positions=None, side=False, count=3):
    positions = positions or (((16.75,24.5),(13.75,24.5),(13.75,24.5),(10.75,24.75)) if args.mirror else ((10.25,24.5),(13.25,24.5),(13.25,24.5),(16.25,24.75)))
    if not args.lan:
        world.commands(("/gamemode survival", f"/item replace entity @s hotbar.0 with create:minecart_coupling {count}"))
        world.call("select", "create:minecart_coupling")
        for x,z in positions:
            px,pz = (x-2,z) if side else (x,z-2)
            world.command(f"/tp @s {px} 170 {pz}")
            world.call("look-at",x,170.2,z); world.call("wait",4); world.call("mouse","right","click"); world.call("wait",3)
        yield world
        return
    network = world.call("lan","open","0","commands","force")
    with TemporaryDirectory(prefix="hc-chain-curve-") as scratch:
        with multiplayer.joined_client(args,Path(scratch),f"127.0.0.1:{network['port']}",GUEST,render=True,scenario="multiplayer-minecart-chain-curve",pack=args.pack,env={"HORIZON_NO_AUDIO":"1","SDL_AUDIODRIVER":"dummy"}) as guest:
            multiplayer.until("guest to join",lambda:any(p["name"] == GUEST and p["placed"] for p in world.call("lan","status")["guests"]))
            world.commands((f"/gamemode survival {GUEST}", f"/item replace entity {GUEST} hotbar.0 with create:minecart_coupling {count}", f"/tp {GUEST} 10.25 170 22.5"))
            multiplayer.until("guest to hold couplings",lambda:multiplayer.count(guest,"create:minecart_coupling") == count)
            guest.call("select","create:minecart_coupling")
            for x,z in positions:
                px,pz = (x-2,z) if side else (x,z-2)
                world.command(f"/tp {GUEST} {px} 170 {pz}")
                multiplayer.until("guest to reach cart",lambda:guest.call("state")["player"]["position"] == [px,170.0,pz])
                guest.call("look-at",x,170.2,z);guest.call("wait",4);guest.call("mouse","right","click");guest.call("wait",3)
            multiplayer.until("two links consumed",lambda:multiplayer.count(guest,"create:minecart_coupling") == 1)
            yield guest

def run(args):
    fixture = "minecart-coupling-chain-curve-mirror-java.csv" if args.mirror else "minecart-coupling-chain-curve-java.csv"
    with (ROOT / "fixtures" / fixture).open(newline="") as f: rows = list(csv.DictReader(f))
    with fixture_world(args, "MinecartChainCurve", pack=args.pack, render=not args.lan) as world:
        commands = ["/fill 4 169 20 22 169 42 minecraft:stone", "/fill 4 170 20 22 173 42 minecraft:air"]
        start, end, corner, shape = (11, 22, 10, "south_east") if args.mirror else (4, 15, 16, "south_west")
        for z in (24, 32):
            commands += [f"/fill {start} 170 {z} {end} 170 {z} minecraft:rail[shape=east_west]", f"/fill {corner} 170 {z+1} {corner} 170 {z+8} minecraft:rail[shape=north_south]", f"/setblock {corner} 170 {z} minecraft:rail[shape={shape}]"]
        commands += [
            '/summon minecraft:minecart 10.25 170.0625 24.5 {UUID:[I;0,0,0,1],Motion:[0.1d,0d,0d],Tags:["chain_a"]}',
            '/summon minecraft:minecart 13.25 170.0625 24.5 {UUID:[I;0,0,0,2],Tags:["chain_b"]}',
            '/summon minecraft:minecart 16.25 170.0625 24.75 {UUID:[I;0,0,0,3],Tags:["chain_c"]}',
            '/summon minecraft:minecart 10.25 170.0625 32.5 {UUID:[I;0,0,0,4],Motion:[0.1d,0d,0d],Tags:["chain_base"]}',
            ]
        if args.mirror:
            commands = [c.replace("10.25 170.0625", "16.75 170.0625").replace("13.25 170.0625", "13.75 170.0625").replace("16.25 170.0625", "10.75 170.0625").replace("Motion:[0.1d", "Motion:[-0.1d") for c in commands]
        world.commands(commands)
        for z in (24, 32):
            block = world.call("block",corner,170,z)
            if f"shape={shape}" not in block["state"]: raise RuntimeError(f"Wrong curve: {block}")
        for i, tag in enumerate(("chain_a", "chain_b", "chain_c", "chain_base"), 1):
            uuid = world.command(f"/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID")
            if f"[I; 0, 0, 0, {i}]" not in uuid: raise RuntimeError(f"Wrong UUID: {uuid}")
        with player_chain(world, args):
            links = world.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]')
            if "Count: 2" not in links: raise RuntimeError(f"Missing links: {links}")
            for row in rows:
                actual = sum((sample(world, tag) for tag in ("chain_a", "chain_b", "chain_c", "chain_base")), [])
                target = [float(row[k]) for k in FIELDS]
                start = 12 if args.base_only else 0
                if any(abs(a-b)>0.00001 for a,b in zip(actual[start:],target[start:])): raise RuntimeError(f"Tick {row['tick']} differs from Java: {actual} vs {target}")
                if int(row["tick"]) != len(rows)-1: world.step_to(world.clock()+1)
    print(f"Matched {len(rows)} mixed-curve Java ticks for {'standalone' if args.base_only else 'chain and standalone'}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"): parser.add_argument(name,type=lambda value:Path(value).resolve(strict=True))
    parser.add_argument("--pack",type=lambda value:Path(value).resolve(strict=True))
    parser.add_argument("--base-only",action="store_true")
    parser.add_argument("--lan",action="store_true")
    parser.add_argument("--mirror",action="store_true")
    run(parser.parse_args())
