#!/usr/bin/env python3
"""Compare a LAN guest's two-cart curve coupling with pinned Create."""
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
        values.extend((float(match.group(1)), float(match.group(3))))
    return values

def run(args, scratch):
    with (ROOT / 'fixtures/minecart-coupling-curve-java.csv').open(newline='') as stream:
        expected = list(csv.DictReader(stream))
    with fixture_world(args, 'MinecartCouplingCurveGuest', pack=args.pack) as host:
        host.commands((
            '/fill 4 169 20 16 169 38 minecraft:stone',
            '/fill 4 170 24 11 170 24 minecraft:rail[shape=east_west]',
            '/fill 12 170 25 12 170 38 minecraft:rail[shape=north_south]',
            '/setblock 12 170 24 minecraft:rail[shape=south_west]',
            '/summon minecraft:minecart 8.5 170.0625 24.5 {UUID:[I;0,0,0,1],Motion:[0.1d,0.0d,0.0d],Tags:["curve_a"]}',
            '/summon minecraft:minecart 11.5 170.0625 24.5 {UUID:[I;0,0,0,2],Tags:["curve_b"]}',
        ))
        for pos, shape in (((11,170,24), 'east_west'), ((12,170,24), 'south_west'), ((12,170,25), 'north_south')):
            block = host.call('block', *pos)
            if f'shape={shape}' not in block['state']: raise RuntimeError(f'Wrong rail at {pos}: {block}')
        for tag, last in (('curve_a', 1), ('curve_b', 2)):
            uuid = host.command(f'/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID')
            if f'[I; 0, 0, 0, {last}]' not in uuid: raise RuntimeError(f'Wrong {tag} UUID: {uuid}')
        network = host.call('lan', 'open', '0', 'commands', 'force')
        with multiplayer.joined_client(args, scratch, f"127.0.0.1:{network['port']}", GUEST, render=True, scenario='multiplayer-minecart-coupling-curve', pack=args.pack) as guest:
            multiplayer.until('guest to join', lambda: any(p['name'] == GUEST and p['placed'] for p in host.call('lan', 'status')['guests']))
            host.commands((f'/gamemode survival {GUEST}', f'/item replace entity {GUEST} hotbar.0 with create:minecart_coupling 2', f'/tp {GUEST} 8.5 170 22.5'))
            multiplayer.until('guest to hold couplings', lambda: multiplayer.count(guest, 'create:minecart_coupling') == 2)
            guest.call('select', 'create:minecart_coupling')
            for x in (8.5, 11.5):
                host.command(f'/tp {GUEST} {x} 170 22.5')
                multiplayer.until('guest to reach cart', lambda: guest.call('state')['player']['position'] == [x, 170.0, 22.5])
                guest.call('look-at', x, 170.2, 24.5)
                guest.call('wait', 4)
                guest.call('mouse', 'right', 'click')
                guest.call('wait', 3)
            multiplayer.until('host to consume coupling', lambda: multiplayer.count(guest, 'create:minecart_coupling') == 1)
            link = host.command('/data get entity @e[type=minecraft:marker,tag=create_minecart_coupling,limit=1] CreateMinecartCoupling')
            if 'Length: 3.0f' not in link: raise RuntimeError(f'No three-block link: {link}')
            fields = ('a_x', 'a_z', 'a_vx', 'a_vz', 'b_x', 'b_z', 'b_vx', 'b_vz')
            for row in expected:
                actual = sample(host, 'curve_a') + sample(host, 'curve_b')
                target = [float(row[key]) for key in fields]
                if any(abs(a-b) > 0.00001 for a,b in zip(actual,target)):
                    raise RuntimeError(f"Tick {row['tick']} differs from Java: {actual} vs {target}")
                if int(row['tick']) != len(expected)-1: host.step_to(host.clock()+1)
    print(f'Guest-created curve coupling matched {len(expected)} Java ticks on the host.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'): parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument('--pack', type=lambda value: Path(value).resolve(strict=True))
    with TemporaryDirectory(prefix='hc-cc-') as scratch: run(parser.parse_args(), Path(scratch))
