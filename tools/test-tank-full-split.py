#!/usr/bin/env python3
"""Compare all ports after removing a filled wider tank controller."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

wide = import_module('test-tank-wide-storage')


def compare(trace, rows, tick, adjacent_pair):
    observed = wide.sample(trace)
    for row in rows:
        if int(row['tick']) != tick:
            continue
        y, dx, dz = (int(row[k]) for k in ('y', 'x', 'z'))
        pos = (9 + dx, 170 + y, 20 + dz)
        if row['block'] == 'minecraft:air':
            assert pos not in observed, (tick, pos, observed[pos])
            continue
        if tick == 9:
            root = pos if dx == 2 and int(row['capacity']) == 8000 else (9, 170, 20)
        elif y == 1 and tick >= 11:
            root = (9, 171, 20)
        elif int(row['capacity']) == 32000:
            root = (10, 170, 20) if adjacent_pair else (9, 170, 21)
        else:
            root = pos
        expected = (root, int(row['capacity']), row['fluid'], int(row['amount']))
        assert observed.get(pos) == expected, (tick, pos, expected, observed.get(pos))


def run(args):
    if (args.adjacent or args.adjacent_pair or args.adjacent_mixed) and (args.amount != 48000 or args.reverse_placement):
        raise ValueError('Adjacent tank is captured only for forward 48,000 mB placement')
    if args.reverse_placement and args.amount != 48000:
        raise ValueError('Reverse placement is captured only for the 48,000 mB 2×2×2 fixture')
    fixture = ('tank-adjacent-mixed-java.csv' if args.adjacent_mixed else
               'tank-adjacent2-java.csv' if args.adjacent_pair else
               'tank-adjacent-java.csv' if args.adjacent else
               'tank-full3-split-java.csv' if args.amount == 120000 else
               'tank-full-split-reverse-java.csv' if args.reverse_placement else
               'tank-full-split-java.csv' if args.amount == 48000 else 'tank-partial-split-java.csv')
    with (ROOT / 'fixtures' / fixture).open() as stream:
        rows = list(csv.DictReader(stream))
    with TemporaryDirectory(prefix='hc-tank-full-split-') as scratch:
        trace = Path(scratch) / 'storage.csv'
        with fixture_world(args, 'TankFullSplit', render=False, pack=args.pack,
                           env={'HORIZON_NO_AUDIO': '1', 'CREATE_TRACE_TANK_STORAGE': str(trace)}) as host:
            y_order = (1, 0) if args.reverse_placement else (0, 1)
            width = 3 if args.amount == 120000 else 2
            order = range(width - 1, -1, -1) if args.reverse_placement else range(width)
            for y_offset in y_order:
                y = 170 + y_offset
                for dx in order:
                    for dz in order:
                        host.call('command', f'/setblock {9 + dx} {y} {20 + dz} create:fluid_tank')
            if args.adjacent or args.adjacent_pair or args.adjacent_mixed:
                host.call('command', '/setblock 11 170 20 create:fluid_tank')
            if args.adjacent_pair or args.adjacent_mixed:
                host.call('command', '/setblock 11 170 21 create:fluid_tank')
            for _ in range(6):
                host.step_to(host.clock() + 1)
            if args.adjacent or args.adjacent_pair or args.adjacent_mixed:
                fluid = 'lava' if args.adjacent_mixed else 'water'
                host.call('command', f'/data merge block 11 170 20 {{TankContent:{{Fluid:{{id:"minecraft:{fluid}",amount:3000}}}}}}')
            if args.adjacent_pair or args.adjacent_mixed:
                host.call('command', f'/data merge block 11 170 21 {{TankContent:{{Fluid:{{id:"minecraft:{fluid}",amount:1000}}}}}}')
            host.call('command', f'/data merge block 9 170 20 {{TankContent:{{Fluid:{{id:"minecraft:water",amount:{args.amount}}}}}}}')
            host.step_to(host.clock() + 1)
            compare(trace, rows, 9, args.adjacent_pair)
            host.call('command', '/setblock 9 170 20 minecraft:air destroy')
            compare(trace, rows, 10, args.adjacent_pair)
            for tick in range(11, 17):
                host.step_to(host.clock() + 1)
                compare(trace, rows, tick, args.adjacent_pair)
    print(f'All {len(rows)} Java high-fill tank controller removal observations matched.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        p.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    p.add_argument('--amount', type=int, choices=(12000, 48000, 120000), default=48000)
    p.add_argument('--reverse-placement', action='store_true')
    adjacency = p.add_mutually_exclusive_group()
    adjacency.add_argument('--adjacent', action='store_true')
    adjacency.add_argument('--adjacent-pair', action='store_true')
    adjacency.add_argument('--adjacent-mixed', action='store_true')
    run(p.parse_args())
