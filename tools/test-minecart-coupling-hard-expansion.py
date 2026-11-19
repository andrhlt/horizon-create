#!/usr/bin/env python3
"""Compare an two-cart hard correction on straight rails with pinned Create."""
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
        match = re.search(key + r': \[([-0-9.eE]+)d', data)
        if not match: raise RuntimeError(f'Missing {key}: {data}')
        values.append(float(match.group(1)))
    return values

def run(args):
    with (ROOT / 'fixtures/minecart-coupling-hard-expansion-java.csv').open(newline='') as stream:
        expected = list(csv.DictReader(stream))
    with fixture_world(args, 'MinecartCouplingHardExpansion', pack=args.pack, render=True) as world:
        world.commands((
            '/fill 4 169 20 24 169 28 minecraft:stone',
            '/fill 4 170 24 24 170 24 minecraft:rail[shape=east_west]',
            '/summon minecraft:minecart 8.5 170.0625 24.5 {Motion:[-0.2d,0.0d,0.0d],Tags:["coupling_a"]}',
            '/summon minecraft:minecart 11.5 170.0625 24.5 {Tags:["coupling_b"]}',
            '/gamemode survival', '/item replace entity @s hotbar.0 with create:minecart_coupling 2',
            '/tp @s 8.5 170 22.5',
        ))
        world.call('select', 'create:minecart_coupling')
        for x in (8.5, 11.5):
            world.command(f'/tp @s {x} 170 22.5')
            world.call('look-at', x, 170.2, 24.5)
            world.call('wait', 4)
            world.call('mouse', 'right', 'click')
            world.call('wait', 3)
        link = world.command('/data get entity @e[type=minecraft:marker,tag=create_minecart_coupling,limit=1] CreateMinecartCoupling')
        if 'Length: 3.0f' not in link: raise RuntimeError(f'No three-block link: {link}')
        for row in expected:
            actual = sample(world, 'coupling_a') + sample(world, 'coupling_b')
            target = [float(row[k]) for k in ('a_x', 'a_velocity', 'b_x', 'b_velocity')]
            if any(abs(a-b) > 0.00001 for a,b in zip(actual,target)):
                raise RuntimeError(f"Tick {row['tick']} differs from Java: {actual} vs {target}")
            if int(row['tick']) != len(expected)-1: world.step_to(world.clock()+1)
    print(f'Matched {len(expected)} ticks of pinned Java hard-correction expansion.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'): parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument('--pack', type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
