#!/usr/bin/env python3
"""Compare north/south ascending-rail pairs and independent carts with Java."""
import argparse
from contextlib import contextmanager
import importlib.util
from tempfile import TemporaryDirectory
import csv
import re
from pathlib import Path
from fixture_world import fixture_world

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('multiplayer', Path(__file__).with_name('test-multiplayer.py'))
multiplayer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multiplayer)
GUEST = 'CouplingGuest'
FIELDS = ('a_z','a_y','a_vz','a_vy','b_z','b_y','b_vz','b_vy','base_z','base_y','base_vz','base_vy')

def sample(world, tag):
    data = world.command(f'/data get entity @e[type=minecraft:minecart,tag={tag},limit=1]')
    values = []
    for key in ('Pos', 'Motion'):
        match = re.search(key + r': \[([-0-9.eE]+)d, ([-0-9.eE]+)d, ([-0-9.eE]+)d\]', data)
        if not match: raise RuntimeError(f'Missing {key}: {data}')
        values.extend((float(match.group(3)), float(match.group(2))))
    return values

@contextmanager
def player_pair(world, args, start_a, start_b):
    if not args.lan:
        world.commands(('/gamemode survival', '/item replace entity @s hotbar.0 with create:minecart_coupling 2', f'/tp @s 22.5 170 {start_a}'))
        world.call('select','create:minecart_coupling')
        for z in (start_a, start_b):
            world.command(f'/tp @s 22.5 170 {z}')
            world.call('look-at',24.5,170.2,z)
            world.call('wait',4)
            world.call('mouse','right','click')
            world.call('wait',3)
        yield
        return
    network = world.call('lan','open','0','commands','force')
    with TemporaryDirectory(prefix='hc-ns-') as scratch:
        with multiplayer.joined_client(args, Path(scratch), f"127.0.0.1:{network['port']}", GUEST, render=True, scenario='multiplayer-minecart-slope-ns', pack=args.pack) as guest:
            multiplayer.until('guest to join', lambda: any(p['name'] == GUEST and p['placed'] for p in world.call('lan','status')['guests']))
            world.commands((f'/gamemode survival {GUEST}', f'/item replace entity {GUEST} hotbar.0 with create:minecart_coupling 2', f'/tp {GUEST} 22.5 170 {start_a}'))
            multiplayer.until('guest to hold couplings', lambda: multiplayer.count(guest,'create:minecart_coupling') == 2)
            guest.call('select','create:minecart_coupling')
            for z in (start_a, start_b):
                world.command(f'/tp {GUEST} 22.5 170 {z}')
                multiplayer.until('guest to reach cart', lambda: guest.call('state')['player']['position'] == [22.5,170.0,z])
                guest.call('look-at',24.5,170.2,z)
                guest.call('wait',4)
                guest.call('mouse','right','click')
                guest.call('wait',3)
            multiplayer.until('host to consume coupling', lambda: multiplayer.count(guest,'create:minecart_coupling') == 1)
            yield

def run_case(args, direction, expected):
    south = direction == 'south'
    start_a, start_b, velocity = (8.5, 11.5, 0.1) if south else (16.5, 13.5, -0.1)
    ids = (1, 2, 3) if south else (4, 5, 6)
    with fixture_world(args, f'MinecartSlope{direction.title()}', pack=args.pack, render=not args.lan) as world:
        commands = ['/fill 20 169 4 30 169 24 minecraft:stone']
        for x in (24, 28):
            commands.append(f'/fill {x} 170 4 {x} 173 24 minecraft:air')
            if south:
                commands += [f'/fill {x} 170 13 {x} 170 24 minecraft:stone',
                             f'/fill {x} 170 4 {x} 170 11 minecraft:rail[shape=north_south]',
                             f'/fill {x} 171 13 {x} 171 24 minecraft:rail[shape=north_south]']
            else:
                commands += [f'/fill {x} 170 4 {x} 170 11 minecraft:stone',
                             f'/fill {x} 170 13 {x} 170 24 minecraft:rail[shape=north_south]',
                             f'/fill {x} 171 4 {x} 171 11 minecraft:rail[shape=north_south]']
            commands.append(f'/setblock {x} 170 12 minecraft:rail[shape=ascending_{direction}]')
        commands += [
            f'/summon minecraft:minecart 24.5 170.0625 {start_a} {{UUID:[I;0,0,0,{ids[0]}],Motion:[0d,0d,{velocity}d],Tags:["slope_a"]}}',
            f'/summon minecraft:minecart 24.5 170.0625 {start_b} {{UUID:[I;0,0,0,{ids[1]}],Tags:["slope_b"]}}',
            f'/summon minecraft:minecart 28.5 170.0625 {start_b} {{UUID:[I;0,0,0,{ids[2]}],Motion:[0d,0d,{velocity}d],Tags:["slope_base"]}}',
        ]
        world.commands(commands)
        for x in (24, 28):
            rails = ((11,170,'north_south'),(12,170,'ascending_south'),(13,171,'north_south')) if south else ((13,170,'north_south'),(12,170,'ascending_north'),(11,171,'north_south'))
            for z, y, shape in rails:
                block = world.call('block', x, y, z)
                if f'shape={shape}' not in block['state']: raise RuntimeError(f'Wrong rail at {x},{y},{z}: {block}')
        for tag, last in zip(('slope_a','slope_b','slope_base'),ids):
            uuid = world.command(f'/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID')
            if f'[I; 0, 0, 0, {last}]' not in uuid: raise RuntimeError(f'Wrong {tag} UUID: {uuid}')
        with player_pair(world, args, start_a, start_b):
            link = world.command('/data get entity @e[type=minecraft:marker,tag=create_minecart_coupling,limit=1] CreateMinecartCoupling')
            if 'Length: 3.0f' not in link: raise RuntimeError(f'No three-block link: {link}')
            for row in expected:
                if args.strong and int(row['tick']) == 13:
                    impulse = 0.3 if south else -0.3
                    for tag in ('slope_b','slope_base'):
                        result = world.command(f'/data merge entity @e[type=minecraft:minecart,tag={tag},limit=1] {{Motion:[0d,0d,{impulse}d]}}')
                        if 'Modified entity data' not in result: raise RuntimeError(f'Impulse failed: {result}')
                actual = sample(world,'slope_a') + sample(world,'slope_b') + sample(world,'slope_base')
                target = [float(row[key]) for key in FIELDS]
                start = 8 if args.base_only else 0
                if any(abs(a-b)>0.00001 for a,b in zip(actual[start:],target[start:])):
                    raise RuntimeError(f"{direction} tick {row['tick']} differs from Java: {actual} vs {target}")
                if int(row['tick']) != len(expected)-1: world.step_to(world.clock()+1)
    print(f'{direction}: matched {len(expected)} Java ticks for {"standalone cart" if args.base_only else "coupled pair and standalone cart"}.')

def run(args):
    fixture = 'minecart-coupling-slope-hard-ns-java.csv' if args.strong else 'minecart-coupling-slope-ns-java.csv'
    with (ROOT / 'fixtures' / fixture).open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    for direction in (('south','north') if args.direction == 'both' else (args.direction,)):
        case = [row for row in rows if row['direction'] == direction]
        if len(case) != 81: raise RuntimeError(f'Wrong Java sample count for {direction}: {len(case)}')
        run_case(args, direction, case)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'): parser.add_argument(name,type=lambda value:Path(value).resolve(strict=True))
    parser.add_argument('--pack',type=lambda value:Path(value).resolve(strict=True))
    parser.add_argument('--direction',choices=('north','south','both'),default='both')
    parser.add_argument('--base-only',action='store_true')
    parser.add_argument('--lan',action='store_true')
    parser.add_argument('--strong',action='store_true')
    run(parser.parse_args())
