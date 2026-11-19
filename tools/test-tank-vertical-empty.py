#!/usr/bin/env python3
"""Replay Java's mixed-fluid vertical column with an empty bottom anchor."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

wide = import_module('test-tank-wide-storage')


def compare(trace, rows, tick, reverse):
    observed = wide.sample(trace)
    for row in rows:
        if int(row['tick']) != tick:
            continue
        rig, y = int(row['rig']), int(row['y'])
        pos = (9 + 6 * rig, 170 + y, 20)
        if row['block'] == 'minecraft:air':
            assert pos not in observed, (tick, pos, observed[pos])
            continue
        root = (pos[0], 170, 20) if tick >= 10 and (not reverse or y < 4) else pos
        expected = (root, int(row['capacity']), row['fluid'], int(row['amount']))
        assert observed.get(pos) == expected, (tick, pos, expected, observed.get(pos))


def run(args):
    fixture = 'tank-vertical-empty-reverse-java.csv' if args.reverse_bridges else 'tank-vertical-empty-java.csv'
    with (ROOT / 'fixtures' / fixture).open() as stream:
        rows = list(csv.DictReader(stream))
    with TemporaryDirectory(prefix='hc-tank-vertical-empty-') as scratch:
        trace = Path(scratch) / 'storage.csv'
        with fixture_world(args, 'TankVerticalEmpty', render=False, pack=args.pack,
                           env={'HORIZON_NO_AUDIO': '1', 'CREATE_TRACE_TANK_STORAGE': str(trace)}) as host:
            for rig in range(2):
                for y in (170, 172, 174):
                    host.call('command', f'/setblock {9 + rig * 6} {y} 20 create:fluid_tank')
            for _ in range(6):
                host.step_to(host.clock() + 1)
            for rig in range(2):
                x = 9 + rig * 6
                for y, fluid, amount in ((172, ('water', 'lava')[rig], 4000), (174, ('lava', 'water')[rig], 5000)):
                    host.call('command', f'/data merge block {x} {y} 20 {{TankContent:{{Fluid:{{id:"minecraft:{fluid}",amount:{amount}}}}}}}')
            host.step_to(host.clock() + 1)
            compare(trace, rows, 9, args.reverse_bridges)
            for rig in range(2):
                x = 9 + 6 * rig
                for y in ((171, 173) if args.reverse_bridges else (173, 171)):
                    host.call('command', f'/setblock {x} {y} 20 create:fluid_tank')
            compare(trace, rows, 10, args.reverse_bridges)
            for tick in range(11, 17):
                host.step_to(host.clock() + 1)
                compare(trace, rows, tick, args.reverse_bridges)
    print('All 80 Java vertical empty-anchor observations matched.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        p.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    p.add_argument('--reverse-bridges', action='store_true')
    run(p.parse_args())
