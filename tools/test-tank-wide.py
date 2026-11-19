#!/usr/bin/env python3
"""Replay Java's 2x2 mixed-fluid tank join, then exercise all joined ports."""
import argparse
import csv
import math
from importlib import import_module
from pathlib import Path
import re
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')
mixed = import_module('test-tank-mixed')


def check(host, rows, tick):
    for row in rows:
        if int(row['tick']) != tick:
            continue
        rig, y, dx, dz = (int(row[k]) for k in ('rig', 'y', 'x', 'z'))
        x = 9 + 6 * rig
        pos = [x + dx, 170 + y, 20 + dz]
        assert host.call('block', *pos)['block'] == row['block'], (row, pos)
        if row['block'] == 'minecraft:air':
            continue
        root_y = 170 if y == 0 else (171 if tick >= 10 else 172)
        tag = host.command(f'/data get block {x} {root_y} 20')
        assert mixed.read(host, x, root_y) == (row['fluid'], int(row['amount'])), (row, tag)
        size = re.search(r'Size: (\d+)', tag)
        height = re.search(r'Height: (\d+)', tag)
        assert size and height and 8000 * int(size[1]) ** 2 * int(height[1]) == int(row['capacity']), (row, tag)


def ports(host, rig, width):
    x = 9 + 6 * rig
    for y in range(3):
        fluid = (('water', 'lava')[rig] if y == 0 else ('lava', 'water')[rig])
        root, amount = (170, 4000) if y == 0 else (171, 5000)
        for dx in range(width):
            for dz in range(width):
                if dx == 0:
                    player_x, player_z, face = x - 1.5, 20 + dz + .5, 'west'
                elif dx == width - 1:
                    player_x, player_z, face = x + width + .5, 20 + dz + .5, 'east'
                elif dz == 0:
                    player_x, player_z, face = x + dx + .5, 18.5, 'north'
                elif dz == width - 1:
                    player_x, player_z, face = x + dx + .5, 20 + width + .5, 'south'
                else:
                    # The central column has no exposed horizontal face.
                    continue
                player_y = 169 + y
                host.call('command', f'/setblock {math.floor(player_x)} {player_y - 1} {math.floor(player_z)} minecraft:stone')
                host.call('command', f'/tp @s {player_x} {player_y} {player_z}')
                mp.until('player positioned', lambda: host.call('state')['player']['position'] == [player_x, player_y, player_z])
                for item, expected in ((fluid + '_bucket', amount + 1000), ('bucket', amount)):
                    host.call('select', f'minecraft:{item}')
                    host.call('interact', x + dx, 170 + y, 20 + dz, face)
                    mp.until('port changes its Java controller', lambda: mixed.read(host, x, root) == (f'minecraft:{fluid}', expected))
                other, other_fluid, other_amount = (171, ('lava', 'water')[rig], 5000) if y == 0 else (170, ('water', 'lava')[rig], 4000)
                assert mixed.read(host, x, other) == (f'minecraft:{other_fluid}', other_amount)


def run(args):
    width = args.width
    fixture = 'tank-wide-java.csv' if width == 2 else 'tank-wide3-java.csv'
    with (ROOT / 'fixtures' / fixture).open() as stream:
        rows = list(csv.DictReader(stream))
    with fixture_world(args, 'TankWide', render=False, pack=args.pack, env={'HORIZON_NO_AUDIO': '1'}) as host:
        host.call('command', '/gamemode creative')
        for slot, item in enumerate(('water_bucket', 'lava_bucket', 'bucket')):
            host.call('command', f'/item replace entity @s hotbar.{slot} with minecraft:{item}')
        for rig in range(2):
            x = 9 + 6 * rig
            for y in (170, 172):
                for dx in range(width):
                    for dz in range(width):
                        host.call('command', f'/setblock {x + dx} {y} {20 + dz} create:fluid_tank')
        for _ in range(6):
            host.step_to(host.clock() + 1)
        for rig in range(2):
            x = 9 + 6 * rig
            for y, fluid, amount in ((170, ('water', 'lava')[rig], 4000), (172, ('lava', 'water')[rig], 5000)):
                host.call('command', f'/data merge block {x} {y} 20 {{TankContent:{{Fluid:{{id:"minecraft:{fluid}",amount:{amount}}}}}}}')
        for tick in range(9, 15):
            if tick == 10:
                for rig in range(2):
                    for dx in range(width):
                        for dz in range(width):
                            host.call('command', f'/setblock {9 + 6 * rig + dx} 171 {20 + dz} create:fluid_tank')
            if tick > 9:
                host.step_to(host.clock() + 1)
            check(host, rows, tick)
            if tick == 11:
                for rig in range(2):
                    ports(host, rig, width)
    print(f'All {36 * width * width} Java join samples matched; all {6 * (width * width - (width - 2) ** 2)} exposed tank ports reached their Java controllers.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        p.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    p.add_argument('--width', type=int, choices=(2, 3), default=2)
    run(p.parse_args())
