#!/usr/bin/env python3
"""Compare every port in Java's same-layer diagonal mixed-fluid tanks."""
import argparse
import csv
import math
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

wide = import_module('test-tank-wide-storage')
mp = import_module('test-multiplayer')


def compare(trace, rows, tick, width, empty_anchor):
    observed = wide.sample(trace)
    for row in rows:
        if int(row['tick']) != tick:
            continue
        rig, dx, dz = (int(row[k]) for k in ('rig', 'x', 'z'))
        pos = (9 + 6 * rig + dx, 170, 20 + dz)
        if row['block'] == 'minecraft:air':
            assert pos not in observed, (tick, pos, observed[pos])
            continue
        grouped = tick >= 10 and ((width == 3 and dx < 2 and dz < 2) or empty_anchor)
        root = (9 + 6 * rig, 170, 20) if grouped else pos
        expected = (root, int(row['capacity']), row['fluid'], int(row['amount']))
        assert observed.get(pos) == expected, (tick, pos, expected, observed.get(pos))


def read(host, x, y, z):
    import re
    tag = host.command(f'/data get block {x} {y} {z}')
    amount = re.search(r'TankContent: \{Fluid: \{[^}]*amount: (\d+)', tag)
    name = re.search(r'TankContent: \{Fluid: \{[^}]*id: "([^"]+)"', tag)
    return (name[1], int(amount[1])) if name and amount else ('minecraft:empty', 0)


def exercise_ports(host, rig, width, empty_anchor):
    x = 9 + rig * 6
    for dx in range(width):
        for dz in range(width):
            if width == 3 and dx == 1 and dz == 1:
                continue
            pos = (x + dx, 170, 20 + dz)
            if dx == 0 or dx == width - 1:
                face = 'west' if dx == 0 else 'east'
                player_x = x - 1.5 if dx == 0 else x + width + .5
                player_z = 20 + dz + .5
            else:
                face = 'north' if dz == 0 else 'south'
                player_x = x + dx + .5
                player_z = 18.5 if dz == 0 else 20 + width + .5
            host.call('command', f'/setblock {math.floor(player_x)} 168 {math.floor(player_z)} minecraft:stone')
            host.call('command', f'/tp @s {player_x} 169 {player_z}')
            mp.until('player positioned', lambda: host.call('state')['player']['position'] == [player_x, 169, player_z])
            if empty_anchor or (dx < 2 and dz < 2 and width == 3):
                name, amount = ('water', 'lava')[rig], 4000
            elif dx == dz == 0:
                name, amount = ('water', 'lava')[rig], 4000
            elif dx == dz == width - 1:
                name, amount = ('lava', 'water')[rig], 5000
            else:
                name, amount = 'water', 0
            root = (x, 170, 20) if empty_anchor or (width == 3 and dx < 2 and dz < 2) else pos
            for item, expected in ((name + '_bucket', amount + 1000), ('bucket', amount)):
                host.call('select', f'minecraft:{item}')
                host.call('interact', *pos, face)
                expected_fluid = f'minecraft:{name}' if expected else 'minecraft:empty'
                mp.until('port changes only itself', lambda: read(host, *root) == (expected_fluid, expected))


def run(args):
    width = args.width
    if args.empty_anchor and width != 2:
        raise ValueError('Empty anchor is captured only for width 2')
    fixture = ('tank-empty-anchor-java.csv' if args.empty_anchor else
               'tank-horizontal-java.csv' if width == 2 else 'tank-horizontal3-java.csv')
    with (ROOT / 'fixtures' / fixture).open() as stream:
        rows = list(csv.DictReader(stream))
    with TemporaryDirectory(prefix='hc-tank-horizontal-') as scratch:
        trace = Path(scratch) / 'storage.csv'
        with fixture_world(args, 'TankHorizontal', render=False, pack=args.pack,
                           env={'HORIZON_NO_AUDIO': '1', 'CREATE_TRACE_TANK_STORAGE': str(trace)}) as host:
            host.call('command', '/gamemode creative')
            for slot, item in enumerate(('water_bucket', 'lava_bucket', 'bucket')):
                host.call('command', f'/item replace entity @s hotbar.{slot} with minecraft:{item}')
            for rig in range(2):
                for corner in range(2):
                    dz = (1 - corner) if args.empty_anchor else corner * (width - 1)
                    host.call('command', f'/setblock {9 + 6 * rig + corner * (width - 1)} 170 {20 + dz} create:fluid_tank')
            for _ in range(6):
                host.step_to(host.clock() + 1)
            for rig in range(2):
                for corner, fluid, amount in ((0, ('water', 'lava')[rig], 4000), (1, ('lava', 'water')[rig], 5000)):
                    dz = (1 - corner) if args.empty_anchor else corner * (width - 1)
                    host.call('command', f'/data merge block {9 + 6 * rig + corner * (width - 1)} 170 {20 + dz} {{TankContent:{{Fluid:{{id:"minecraft:{fluid}",amount:{amount}}}}}}}')
            host.step_to(host.clock() + 1)
            compare(trace, rows, 9, width, args.empty_anchor)
            for rig in range(2):
                x = 9 + 6 * rig
                for dx in range(width):
                    for dz in range(width):
                        initial = ((0, 1), (1, 0)) if args.empty_anchor else ((0, 0), (width - 1, width - 1))
                        if (dx, dz) in initial:
                            continue
                        host.call('command', f'/setblock {x + dx} 170 {20 + dz} create:fluid_tank')
            compare(trace, rows, 10, width, args.empty_anchor)
            if args.empty_anchor:
                for rig in range(2):
                    assert read(host, 10 + 6 * rig, 170, 20) == ('minecraft:empty', 0)
            for tick in range(11, 17):
                host.step_to(host.clock() + 1)
                compare(trace, rows, tick, width, args.empty_anchor)
                if tick == 11 and not args.storage_only:
                    for rig in range(2):
                        exercise_ports(host, rig, width, args.empty_anchor)
    print(f'All {16 * width * width} Java observations matched' + ('.' if args.storage_only else ', including exposed physical ports.'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        p.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    p.add_argument('--width', type=int, choices=(2, 3), default=2)
    p.add_argument('--storage-only', action='store_true')
    p.add_argument('--empty-anchor', action='store_true')
    run(p.parse_args())
