#!/usr/bin/env python3
"""Compare coupled and independent carts approaching an ascending rail."""
import argparse
import csv
import re
from pathlib import Path
from fixture_world import fixture_world

ROOT = Path(__file__).resolve().parents[1]

def sample(world, tag):
    data = world.command(f'/data get entity @e[type=minecraft:minecart,tag={tag},limit=1]')
    values = []
    for key in ('Pos', 'Motion'):
        match = re.search(key + r': \[([-0-9.eE]+)d, ([-0-9.eE]+)d, ([-0-9.eE]+)d\]', data)
        if not match: raise RuntimeError(f'Missing {key}: {data}')
        values.extend((float(match.group(1)), float(match.group(2))))
    return values

def run(args):
    with (ROOT / 'fixtures/minecart-coupling-slope-java.csv').open(newline='') as stream:
        expected = list(csv.DictReader(stream))
    with fixture_world(args, 'MinecartCouplingSlope', pack=args.pack, render=True) as world:
        commands = ['/fill 4 169 20 24 169 30 minecraft:stone']
        for z in (24, 28):
            commands += [f'/fill 4 170 {z} 24 173 {z} minecraft:air',
                         f'/fill 13 170 {z} 24 170 {z} minecraft:stone',
                         f'/fill 4 170 {z} 11 170 {z} minecraft:rail[shape=east_west]',
                         f'/fill 13 171 {z} 24 171 {z} minecraft:rail[shape=east_west]',
                         f'/setblock 12 170 {z} minecraft:rail[shape=ascending_east]']
        commands += [
            '/summon minecraft:minecart 8.5 170.0625 24.5 {UUID:[I;0,0,0,1],Motion:[0.1d,0d,0d],Tags:["slope_a"]}',
            '/summon minecraft:minecart 11.5 170.0625 24.5 {UUID:[I;0,0,0,2],Tags:["slope_b"]}',
            '/summon minecraft:minecart 11.5 170.0625 28.5 {UUID:[I;0,0,0,3],Motion:[0.1d,0d,0d],Tags:["slope_base"]}',
            '/gamemode survival', '/item replace entity @s hotbar.0 with create:minecart_coupling 2', '/tp @s 8.5 170 22.5',
        ]
        world.commands(commands)
        for z in (24, 28):
            for x, y, shape in ((11,170,'east_west'), (12,170,'ascending_east'), (13,171,'east_west')):
                block = world.call('block', x, y, z)
                if f'shape={shape}' not in block['state']: raise RuntimeError(f'Wrong rail at {x},{y},{z}: {block}')
        for tag, last in (('slope_a',1), ('slope_b',2), ('slope_base',3)):
            uuid = world.command(f'/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID')
            if f'[I; 0, 0, 0, {last}]' not in uuid: raise RuntimeError(f'Wrong {tag} UUID: {uuid}')
        world.call('select', 'create:minecart_coupling')
        for x in (8.5, 11.5):
            world.command(f'/tp @s {x} 170 22.5')
            world.call('look-at', x, 170.2, 24.5)
            world.call('wait', 4)
            world.call('mouse', 'right', 'click')
            world.call('wait', 3)
        link = world.command('/data get entity @e[type=minecraft:marker,tag=create_minecart_coupling,limit=1] CreateMinecartCoupling')
        if 'Length: 3.0f' not in link: raise RuntimeError(f'No three-block link: {link}')
        fields = ('a_x','a_y','a_vx','a_vy','b_x','b_y','b_vx','b_vy','base_x','base_y','base_vx','base_vy')
        for row in expected:
            actual = sample(world, 'slope_a') + sample(world, 'slope_b') + sample(world, 'slope_base')
            target = [float(row[key]) for key in fields]
            start = 8 if args.base_only else 0
            if any(abs(a-b) > 0.00001 for a,b in zip(actual[start:],target[start:])):
                raise RuntimeError(f"Tick {row['tick']} differs from Java: {actual} vs {target}")
            if int(row['tick']) != len(expected)-1: world.step_to(world.clock()+1)
    print(f'Matched {len(expected)} Java slope ticks for {"the standalone cart" if args.base_only else "the standalone cart and coupled pair"}.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'): parser.add_argument(name,type=lambda value:Path(value).resolve(strict=True))
    parser.add_argument('--pack',type=lambda value:Path(value).resolve(strict=True))
    parser.add_argument('--base-only',action='store_true')
    run(parser.parse_args())
