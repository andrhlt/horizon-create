#!/usr/bin/env python3
"""Compare a player-coupled pair on two curve rails with pinned Create."""
import argparse
import csv
from contextlib import contextmanager
import importlib.util
from tempfile import TemporaryDirectory
import re
from pathlib import Path
from fixture_world import fixture_world

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('multiplayer', Path(__file__).with_name('test-multiplayer.py'))
multiplayer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multiplayer)
GUEST = 'CouplingGuest'
FIELDS = ('a_x','a_z','a_vx','a_vz','b_x','b_z','b_vx','b_vz','base_x','base_z','base_vx','base_vz')

def sample(world, tag):
    data = world.command(f'/data get entity @e[type=minecraft:minecart,tag={tag},limit=1]')
    values = []
    for key in ('Pos', 'Motion'):
        match = re.search(key + r': \[([-0-9.eE]+)d, ([-0-9.eE]+)d, ([-0-9.eE]+)d\]', data)
        if not match: raise RuntimeError(f'Missing {key}: {data}')
        values.extend((float(match.group(1)), float(match.group(3))))
    return values

@contextmanager
def player_pair(world, args):
    if not args.lan:
        world.commands(('/gamemode survival', '/item replace entity @s hotbar.0 with create:minecart_coupling 2'))
        player = world
        for x in (8.95, 12.05):
            world.command(f'/tp @s {x} 170 22.55')
            player.call('select','create:minecart_coupling')
            player.call('look-at',x,170.2,24.55)
            player.call('wait',4)
            player.call('mouse','right','click')
            player.call('wait',3)
        yield
        return
    network = world.call('lan','open','0','commands','force')
    with TemporaryDirectory(prefix='hc-two-curves-') as scratch:
        with multiplayer.joined_client(args, Path(scratch), f"127.0.0.1:{network['port']}", GUEST, render=True, scenario='multiplayer-minecart-two-curves', pack=args.pack) as guest:
            multiplayer.until('guest to join', lambda: any(p['name'] == GUEST and p['placed'] for p in world.call('lan','status')['guests']))
            world.commands((f'/gamemode survival {GUEST}', f'/item replace entity {GUEST} hotbar.0 with create:minecart_coupling 2', f'/tp {GUEST} 8.95 170 22.55'))
            multiplayer.until('guest to hold couplings', lambda: multiplayer.count(guest,'create:minecart_coupling') == 2)
            guest.call('select','create:minecart_coupling')
            for x in (8.95, 12.05):
                world.command(f'/tp {GUEST} {x} 170 22.55')
                multiplayer.until('guest to reach cart', lambda: guest.call('state')['player']['position'] == [x,170.0,22.55])
                guest.call('look-at',x,170.2,24.55)
                guest.call('wait',4)
                guest.call('mouse','right','click')
                guest.call('wait',3)
            multiplayer.until('host to consume coupling', lambda: multiplayer.count(guest,'create:minecart_coupling') == 1)
            yield

def run(args):
    fixture = 'minecart-coupling-two-curves-hard-java.csv' if args.strong else 'minecart-coupling-two-curves-java.csv'
    with (ROOT / 'fixtures' / fixture).open(newline='') as stream:
        expected = list(csv.DictReader(stream))
    if not 1 <= args.ticks <= len(expected): raise ValueError(f'--ticks must be between 1 and {len(expected)}')
    with fixture_world(args, 'MinecartCouplingTwoCurves', pack=args.pack, render=not args.lan) as world:
        commands = ['/fill 4 169 20 16 169 40 minecraft:stone', '/fill 4 170 20 16 173 40 minecraft:air']
        for z in (24,32):
            commands.append(f'/fill 9 170 {z} 11 170 {z} minecraft:rail[shape=east_west]')
            for x in (8,12): commands.append(f'/fill {x} 170 {z+1} {x} 170 {z+5} minecraft:rail[shape=north_south]')
            commands += [f'/setblock 8 170 {z} minecraft:rail[shape=south_east]', f'/setblock 12 170 {z} minecraft:rail[shape=south_west]']
        speed = '0.03' if args.strong else '0.005'
        commands += [
            f'/summon minecraft:minecart 8.95 170.0625 24.55 {{UUID:[I;0,0,0,1],Motion:[-{speed}d,0d,{speed}d],Tags:["curve_a"]}}',
            f'/summon minecraft:minecart 12.05 170.0625 24.55 {{UUID:[I;0,0,0,2],Motion:[{speed}d,0d,{speed}d],Tags:["curve_b"]}}',
            f'/summon minecraft:minecart 8.95 170.0625 32.55 {{UUID:[I;0,0,0,3],Motion:[-{speed}d,0d,{speed}d],Tags:["curve_base"]}}',
        ]
        world.commands(commands)
        for z in (24,32):
            for x, shape in ((8,'south_east'),(12,'south_west')):
                block = world.call('block',x,170,z)
                if f'shape={shape}' not in block['state']: raise RuntimeError(f'Wrong curve at {x},{z}: {block}')
        for tag,last in (('curve_a',1),('curve_b',2),('curve_base',3)):
            uuid = world.command(f'/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID')
            if f'[I; 0, 0, 0, {last}]' not in uuid: raise RuntimeError(f'Wrong {tag} UUID: {uuid}')
        with player_pair(world, args):
            link = world.command('/data get entity @e[type=minecraft:marker,tag=create_minecart_coupling,limit=1] CreateMinecartCoupling')
            if 'Length: 3.0f' not in link: raise RuntimeError(f'No three-block link: {link}')
            for row in expected[:args.ticks]:
                actual = sample(world,'curve_a') + sample(world,'curve_b') + sample(world,'curve_base')
                target = [float(row[key]) for key in FIELDS]
                start = 8 if args.base_only else 0
                end = 8 if args.pair_only else len(FIELDS)
                if any(abs(a-b)>0.00001 for a,b in zip(actual[start:end],target[start:end])):
                    raise RuntimeError(f"Tick {row['tick']} differs from Java: {actual} vs {target}")
                if int(row['tick']) != args.ticks-1: world.step_to(world.clock()+1)
    print(f'Matched {args.ticks} Java two-curve ticks for {"standalone cart" if args.base_only else "coupled pair" if args.pair_only else "coupled pair and standalone cart"}.')

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'): parser.add_argument(name,type=lambda value:Path(value).resolve(strict=True))
    parser.add_argument('--pack',type=lambda value:Path(value).resolve(strict=True))
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--base-only',action='store_true')
    group.add_argument('--pair-only',action='store_true')
    parser.add_argument('--lan',action='store_true')
    parser.add_argument('--strong',action='store_true')
    parser.add_argument('--ticks',type=int,default=81)
    run(parser.parse_args())
