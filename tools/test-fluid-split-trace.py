#!/usr/bin/env python3
"""Compare a Create fluid pumped through Create's three-way pipe fixture."""
import argparse
import csv
from pathlib import Path
import re
from fixture_world import ROOT, fixture_world

SOURCE = '4 97 -10'
TANKS = ('8 97 -11', '8 97 -10', '8 97 -9')

def amount(value, fluid):
    match = re.search(r'\bamount:\s*(\d+)', value)
    if match and f'id: "create:{fluid}"' not in value:
        raise AssertionError(f'Expected {fluid}: {value}')
    return int(match[1]) if match else 0

def tank_state(host, fluid):
    source, *tanks = host.commands(f'/data get block {at} TankContent' for at in (SOURCE, *TANKS))
    return amount(source, fluid), sum(amount(tank, fluid) for tank in tanks)

def advance(host, ticks):
    start = host.clock()
    host.command(f'/tick step {ticks}')
    for _ in range(200):
        now = host.clock()
        if now == start + ticks:
            return
        if now > start + ticks:
            raise RuntimeError(f'Expected game tick {start + ticks}, got {now}')
    raise RuntimeError(f'Server did not advance {ticks} ticks')

def run(args):
    rows = rows_for(args.fluid)
    if args.reopen and not any(int(row['tick']) == args.reopen_at for row in rows):
        raise ValueError(f'No Java reference sample at reopen tick {args.reopen_at}')
    with fixture_world(args, f'{args.fluid.title()} Pipe Split', Path('gametest/fluids/3_pipe_split.nbt'), pack=args.pack) as host:
        host.command('/place template create:gametest/fluids/3_pipe_split 3 96 -12')
        host.command(f'/data merge block {SOURCE} {{TankContent:{{Fluid:{{id:"create:{args.fluid}",amount:11000}}}}}}')
        host.command('/setblock 5 97 -10 create:mechanical_pump[facing=west,waterlogged=false]')
        if args.reopen:
            host.commands((
                '/setblock 14 97 -10 create:fluid_tank',
                '/data merge block 14 97 -10 {TankContent:{Fluid:{id:"create:chocolate",amount:1000}}}',
            ))
        start = host.clock()
        resumed = False
        matched = 0
        for row in rows:
            tick = int(row['tick'])
            if tick:
                host.step_to(start + tick)
            actual = tank_state(host, args.fluid)
            expected = int(row['source']), int(row['destinations'])
            if actual != expected:
                raise AssertionError(f'Tick {tick}: Horizon {actual}; Java {expected}')
            matched += 1
            if args.reopen and tick == args.reopen_at:
                chocolate = host.command('/data get block 14 97 -10 TankContent')
                if amount(chocolate, 'chocolate') != 1000:
                    raise AssertionError(f'Chocolate sentinel before reopen: {chocolate}')
                host.call('save')
                host.restart()
                after_reopen = tank_state(host, args.fluid)
                if sum(after_reopen) != 11000:
                    raise AssertionError(f'Active {args.fluid} amount was lost on reopen: {actual} -> {after_reopen}')
                chocolate = host.command('/data get block 14 97 -10 TankContent')
                if amount(chocolate, 'chocolate') != 1000:
                    raise AssertionError(f'Chocolate identity/amount after reopen: {chocolate}')
                advance(host, 100)
                continued = tank_state(host, args.fluid)
                if continued[0] + continued[1] != 11000 or continued[1] <= after_reopen[1]:
                    raise AssertionError(f'{args.fluid} transfer did not resume after reopen: {after_reopen} -> {continued}')
                resumed = True
                break
    suffix = f' (active reopen at tick {args.reopen_at}; transfer resumed)' if resumed else ''
    print(f'{args.fluid.title()} source and combined destinations matched {matched} Java ticks{suffix}.')

def rows_for(fluid):
    with (ROOT / f'fixtures/{fluid}-pipe-java.csv').open() as source:
        rows = list(csv.DictReader(source))
    return rows

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=lambda path: Path(path).resolve(strict=True), default=ROOT / ".local/create.hmod")
    parser.add_argument('--fluid', required=True, choices=('honey', 'tea'))
    parser.add_argument('--reopen', action='store_true')
    parser.add_argument('--reopen-at', type=int, default=50)
    run(parser.parse_args())
