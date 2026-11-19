#!/usr/bin/env python3
"""Replay Java's filled flat 2×2 tank controller and member removal."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

wide = import_module('test-tank-wide-storage')
horizontal = import_module('test-tank-horizontal')
mp = import_module('test-multiplayer')


def compare(trace, rows, tick):
    observed = wide.sample(trace)
    for row in rows:
        if int(row['tick']) != tick:
            continue
        rig, dx, dz = (int(row[k]) for k in ('rig', 'x', 'z'))
        pos = (9 + 6 * rig + dx, 170, 20 + dz)
        if row['block'] == 'minecraft:air':
            assert pos not in observed, (tick, pos, observed[pos])
            continue
        root = (9 + 6 * rig, 170, 20) if tick == 9 else pos
        expected = (root, int(row['capacity']), row['fluid'], int(row['amount']))
        assert observed.get(pos) == expected, (tick, pos, expected, observed.get(pos))


def run(args):
    with (ROOT / 'fixtures/tank-flat-split-java.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    with TemporaryDirectory(prefix='hc-tank-flat-split-') as scratch:
        trace = Path(scratch) / 'storage.csv'
        with fixture_world(args, 'TankFlatSplit', render=False, pack=args.pack,
                           env={'HORIZON_NO_AUDIO': '1', 'CREATE_TRACE_TANK_STORAGE': str(trace)}) as host:
            for rig in range(2):
                for dx in range(2):
                    for dz in range(2):
                        host.call('command', f'/setblock {9 + 6 * rig + dx} 170 {20 + dz} create:fluid_tank')
            for _ in range(6):
                host.step_to(host.clock() + 1)
            for x in (9, 15):
                host.call('command', f'/data merge block {x} 170 20 {{TankContent:{{Fluid:{{id:"minecraft:water",amount:24000}}}}}}')
            host.step_to(host.clock() + 1)
            compare(trace, rows, 9)
            for x, z, player_x in ((9, 20, 7.5), (16, 21, 18.5)):
                if args.player:
                    host.call('command', f'/setblock {int(player_x)} 168 {z} minecraft:stone')
                    host.call('command', f'/gamemode creative')
                    host.call('command', f'/tp @s {player_x} 169 {z + .5}')
                    mp.until('player positioned', lambda: host.call('state')['player']['position'] == [player_x, 169, z + .5])
                    host.call('look-at', x + .5, 170.5, z + .5)
                    mp.until('tank targeted', lambda: (host.call('looking-at').get('block') or {}).get('pos') == [x, 170, z])
                    host.call('mouse', 'left', 'click')
                    mp.until('tank mined', lambda: host.call('block', x, 170, z)['block'] == 'minecraft:air')
                else:
                    host.call('command', f'/setblock {x} 170 {z} minecraft:air destroy')
            if args.player:
                for row in rows:
                    if int(row['tick']) != 10 or row['block'] == 'minecraft:air':
                        continue
                    rig, dx, dz = (int(row[k]) for k in ('rig', 'x', 'z'))
                    pos = (9 + 6 * rig + dx, 170, 20 + dz)
                    expected = (row['fluid'], int(row['amount']))
                    assert horizontal.read(host, *pos) == expected, (pos, expected, horizontal.read(host, *pos))
            else:
                compare(trace, rows, 10)
            for tick in range(11, 17):
                host.step_to(host.clock() + 1)
                compare(trace, rows, tick)
    print('All 64 Java flat-tank controller and member removal observations matched.')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        p.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    p.add_argument('--player', action='store_true')
    run(p.parse_args())
