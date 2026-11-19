#!/usr/bin/env python3
"""Compare a LAN guest's coupled pair and a standalone cart on a slope."""
import argparse
import csv
import importlib.util
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import fixture_world

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('multiplayer', Path(__file__).with_name('test-multiplayer.py'))
multiplayer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multiplayer)
GUEST = 'CouplingGuest'

def sample(world, tag):
    data = world.command(f'/data get entity @e[type=minecraft:minecart,tag={tag},limit=1]')
    values = []
    for key in ('Pos', 'Motion'):
        match = re.search(key + r': \[([-0-9.eE]+)d, ([-0-9.eE]+)d, ([-0-9.eE]+)d\]', data)
        if not match: raise RuntimeError(f'Missing {key}: {data}')
        values.extend((float(match.group(1)), float(match.group(2))))
    return values

def run(args, scratch):
    fixture = 'minecart-coupling-slope-hard-west-java.csv' if args.strong else 'minecart-coupling-slope-west-java.csv'
    with (ROOT / 'fixtures' / fixture).open(newline='') as stream:
        expected = list(csv.DictReader(stream))
    with fixture_world(args, 'MinecartCouplingSlopeWestGuest', pack=args.pack) as host:
        commands = ['/fill 4 169 20 24 169 30 minecraft:stone']
        for z in (24, 28):
            commands += [f'/fill 4 170 {z} 24 173 {z} minecraft:air',
                         f'/fill 4 170 {z} 11 170 {z} minecraft:stone',
                         f'/fill 13 170 {z} 24 170 {z} minecraft:rail[shape=east_west]',
                         f'/fill 4 171 {z} 11 171 {z} minecraft:rail[shape=east_west]',
                         f'/setblock 12 170 {z} minecraft:rail[shape=ascending_west]']
        commands += [
            '/summon minecraft:minecart 16.5 170.0625 24.5 {UUID:[I;0,0,0,1],Motion:[-0.1d,0d,0d],Tags:["slope_a"]}',
            '/summon minecraft:minecart 13.5 170.0625 24.5 {UUID:[I;0,0,0,2],Tags:["slope_b"]}',
            '/summon minecraft:minecart 13.5 170.0625 28.5 {UUID:[I;0,0,0,3],Motion:[-0.1d,0d,0d],Tags:["slope_base"]}',
        ]
        host.commands(commands)
        for z in (24, 28):
            for x, y, shape in ((13,170,'east_west'), (12,170,'ascending_west'), (11,171,'east_west')):
                block = host.call('block', x, y, z)
                if f'shape={shape}' not in block['state']: raise RuntimeError(f'Wrong rail at {x},{y},{z}: {block}')
        for tag, last in (('slope_a',1), ('slope_b',2), ('slope_base',3)):
            uuid = host.command(f'/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID')
            if f'[I; 0, 0, 0, {last}]' not in uuid: raise RuntimeError(f'Wrong {tag} UUID: {uuid}')
        network = host.call('lan', 'open', '0', 'commands', 'force')
        with multiplayer.joined_client(args, scratch, f"127.0.0.1:{network['port']}", GUEST, render=True, scenario='multiplayer-minecart-coupling-slope-west', pack=args.pack) as guest:
            multiplayer.until('guest to join', lambda: any(p['name'] == GUEST and p['placed'] for p in host.call('lan', 'status')['guests']))
            host.commands((f'/gamemode survival {GUEST}', f'/item replace entity {GUEST} hotbar.0 with create:minecart_coupling 2', f'/tp {GUEST} 16.5 170 22.5'))
            multiplayer.until('guest to hold couplings', lambda: multiplayer.count(guest, 'create:minecart_coupling') == 2)
            guest.call('select', 'create:minecart_coupling')
            for x in (16.5, 13.5):
                host.command(f'/tp {GUEST} {x} 170 22.5')
                multiplayer.until('guest to reach cart', lambda: guest.call('state')['player']['position'] == [x, 170.0, 22.5])
                guest.call('look-at', x, 170.2, 24.5)
                guest.call('wait', 4)
                guest.call('mouse', 'right', 'click')
                guest.call('wait', 3)
            multiplayer.until('host to consume coupling', lambda: multiplayer.count(guest, 'create:minecart_coupling') == 1)
            link = host.command('/data get entity @e[type=minecraft:marker,tag=create_minecart_coupling,limit=1] CreateMinecartCoupling')
            if 'Length: 3.0f' not in link: raise RuntimeError(f'No three-block link: {link}')
            fields = ('a_x','a_y','a_vx','a_vy','b_x','b_y','b_vx','b_vy','base_x','base_y','base_vx','base_vy')
            for row in expected:
                if args.strong and int(row['tick']) == 13:
                    for tag in ('slope_b','slope_base'):
                        result = host.command(f'/data merge entity @e[type=minecraft:minecart,tag={tag},limit=1] {{Motion:[-0.3d,0d,0d]}}')
                        if 'Modified entity data' not in result: raise RuntimeError(f'Impulse failed: {result}')
                actual = sample(host, 'slope_a') + sample(host, 'slope_b') + sample(host, 'slope_base')
                target = [float(row[key]) for key in fields]
                if any(abs(a-b) > 0.00001 for a,b in zip(actual,target)):
                    raise RuntimeError(f"Tick {row['tick']} differs from Java: {actual} vs {target}")
                if int(row['tick']) != len(expected)-1: host.step_to(host.clock()+1)
    print(f'Guest-created slope coupling and standalone cart matched {len(expected)} Java ticks on the host.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'): parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument('--pack', type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument('--strong', action='store_true')
    with TemporaryDirectory(prefix='hc-ms-') as scratch: run(parser.parse_args(), Path(scratch))
