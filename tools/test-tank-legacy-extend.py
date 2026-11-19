#!/usr/bin/env python3
"""Reopen a pre-ownership mixed tank world and extend its upper groups."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

wide = import_module('test-tank-wide-storage')
mp = import_module('test-multiplayer')
mixed = import_module('test-tank-mixed')


def compare(trace, rows, tick):
    observed = wide.sample(trace)
    for row in rows:
        if int(row['tick']) != tick:
            continue
        rig, y = int(row['rig']), int(row['y'])
        pos = (9 + 6 * rig, 170 + y, 20)
        if row['block'] == 'minecraft:air':
            assert pos not in observed, (tick, pos, observed[pos])
            continue
        root_y = 170 if y == 0 else (171 if tick >= 10 else 172 + (y - 2))
        expected = ((pos[0], root_y, 20), int(row['capacity']), row['fluid'], int(row['amount']))
        assert observed.get(pos) == expected, (tick, pos, expected, observed.get(pos))


def run(args):
    with (ROOT / 'fixtures/tank-legacy-extend-java.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    new_client = args.client
    args.client = args.old_client
    with TemporaryDirectory(prefix='hc-tank-legacy-') as scratch:
        trace = Path(scratch) / 'storage.csv'
        with fixture_world(args, 'TankLegacyExtend', render=False, pack=args.pack,
                           env={'HORIZON_NO_AUDIO': '1', 'CREATE_TRACE_TANK_STORAGE': str(trace)}) as host:
            for rig in range(2):
                x = 9 + 6 * rig
                for y in (170, 172):
                    host.call('command', f'/setblock {x} {y} 20 create:fluid_tank')
            for _ in range(6):
                host.step_to(host.clock() + 1)
            for rig in range(2):
                x = 9 + 6 * rig
                for y, fluid, amount in ((170, ('water', 'lava')[rig], 4000), (172, ('lava', 'water')[rig], 5000)):
                    host.call('command', f'/data merge block {x} {y} 20 {{TankContent:{{Fluid:{{id:"minecraft:{fluid}",amount:{amount}}}}}}}')
                host.call('command', f'/setblock {x} 171 20 create:fluid_tank')
            for _ in range(3):
                host.step_to(host.clock() + 1)
            host.restart(client=new_client)
            # Allow the cold launcher to load and freeze, then observe a complete BE phase.
            host.step_to(host.clock() + 1)
            compare(trace, rows, 11)
            if args.player:
                host.call('command', '/gamemode creative')
                for slot, item in enumerate(('create:fluid_tank', 'minecraft:water_bucket', 'minecraft:lava_bucket', 'minecraft:bucket')):
                    host.call('command', f'/item replace entity @s hotbar.{slot} with {item}')
            for rig in range(2):
                x = 9 + 6 * rig
                if args.player:
                    host.call('command', f'/setblock {x} 172 23 minecraft:stone')
                    host.call('command', f'/tp @s {x + .5} 173 23.5')
                    mp.until('player positioned', lambda: host.call('state')['player']['position'] == [x + .5, 173, 23.5])
                    host.call('select', 'create:fluid_tank')
                    host.call('interact', x, 172, 20, 'up')
                    assert host.call('block', x, 173, 20)['block'] == 'create:fluid_tank'
                    fluid = ('lava', 'water')[rig]
                    assert mixed.read(host, x, 171) == (f'minecraft:{fluid}', 5000)
                    for item, amount in ((fluid + '_bucket', 6000), ('bucket', 5000)):
                        host.call('select', f'minecraft:{item}')
                        host.call('interact', x, 173, 20, 'up')
                        mp.until('extended port reaches old controller', lambda: mixed.read(host, x, 171) == (f'minecraft:{fluid}', amount))
                else:
                    host.call('command', f'/setblock {x} 173 20 create:fluid_tank')
            if not args.player:
                compare(trace, rows, 12)
            for tick in range(13, 17):
                host.step_to(host.clock() + 1)
                compare(trace, rows, tick)
    print('Pre-ownership mixed tank groups survived cold reopen and extended at the Java boundary in both fluid orders.')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        p.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument('--old-client', type=lambda path: Path(path).resolve(strict=True), required=True)
    p.add_argument('--player', action='store_true')
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(p.parse_args())
