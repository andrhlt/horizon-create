#!/usr/bin/env python3
"""Compare every wider tank's actual storage after each block-entity tick."""
import argparse
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world


def sample(path):
    rows = list(csv.reader(path.open()))
    start = max(i for i, row in enumerate(rows) if row and row[0] == 'snapshot')
    return {(int(r[1]), int(r[2]), int(r[3])): (tuple(map(int, r[4:7])), int(r[7]), r[8], int(r[9]))
            for r in rows[start + 1:]}


def compare(observed, rows, tick):
    for row in rows:
        if int(row['tick']) != tick:
            continue
        rig, y, dx, dz = (int(row[k]) for k in ('rig', 'y', 'x', 'z'))
        x = 9 + 6 * rig
        pos = (x + dx, 170 + y, 20 + dz)
        if row['block'] == 'minecraft:air':
            assert pos not in observed, (tick, pos, observed[pos])
            continue
        if tick == 15 and y == 2:
            root = pos
        else:
            root_y = 170 if y == 0 else (171 if 10 <= tick <= 14 else 172)
            root = (x, root_y, 20)
        expected = (root, int(row['capacity']), row['fluid'], int(row['amount']))
        assert observed.get(pos) == expected, (tick, pos, expected, observed.get(pos))


def run(args):
    width = args.width
    fixture = 'tank-wide-java.csv' if width == 2 else 'tank-wide3-java.csv'
    with (ROOT / 'fixtures' / fixture).open() as f:
        rows = list(csv.DictReader(f))
    with TemporaryDirectory(prefix='hc-tank-storage-') as scratch:
        trace = Path(scratch) / 'storage.csv'
        with fixture_world(args, 'TankWideStorage', render=False, pack=args.pack,
                           env={'HORIZON_NO_AUDIO': '1', 'CREATE_TRACE_TANK_STORAGE': str(trace)}) as host:
            for rig in range(2):
                for y in (170, 172):
                    for dx in range(width):
                        for dz in range(width):
                            host.call('command', f'/setblock {9 + rig * 6 + dx} {y} {20 + dz} create:fluid_tank')
            for _ in range(6):
                host.step_to(host.clock() + 1)
            for rig in range(2):
                x = 9 + rig * 6
                for y, fluid, amount in ((170, ('water', 'lava')[rig], 4000), (172, ('lava', 'water')[rig], 5000)):
                    host.call('command', f'/data merge block {x} {y} 20 {{TankContent:{{Fluid:{{id:"minecraft:{fluid}",amount:{amount}}}}}}}')
            host.step_to(host.clock() + 1)
            compare(sample(trace), rows, 9)
            for rig in range(2):
                for dx in range(width):
                    for dz in range(width):
                        host.call('command', f'/setblock {9 + rig * 6 + dx} 171 {20 + dz} create:fluid_tank')
            # Java samples the join immediately after the last placement.
            compare(sample(trace), rows, 10)
            for tick in range(11, 15):
                host.step_to(host.clock() + 1)
                compare(sample(trace), rows, tick)
            for rig in range(2):
                for dx in range(width):
                    for dz in range(width):
                        host.call('command', f'/setblock {9 + rig * 6 + dx} 171 {20 + dz} minecraft:air destroy')
            # Java samples the split immediately after the last removal.
            compare(sample(trace), rows, 15)
            for tick in range(16, 20):
                host.step_to(host.clock() + 1)
                compare(sample(trace), rows, tick)
    print(f'Every {width}×{width} tank port matched Java storage at each Java join and separation boundary and subsequent ticks.')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        p.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    p.add_argument('--width', type=int, choices=(2, 3), default=2)
    run(p.parse_args())
