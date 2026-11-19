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

def run(args):
    with (ROOT / f'fixtures/{args.fluid}-pipe-java.csv').open() as source:
        rows = list(csv.DictReader(source))
    with fixture_world(args, f'{args.fluid.title()} Pipe Split', Path('gametest/fluids/3_pipe_split.nbt'), pack=args.pack) as host:
        host.command('/place template create:gametest/fluids/3_pipe_split 3 96 -12')
        host.command(f'/data merge block {SOURCE} {{TankContent:{{Fluid:{{id:"create:{args.fluid}",amount:11000}}}}}}')
        host.command('/setblock 5 97 -10 create:mechanical_pump[facing=west,waterlogged=false]')
        start = host.clock()
        for row in rows:
            tick = int(row['tick'])
            if tick:
                host.step_to(start + tick)
            source, *tanks = host.commands(f'/data get block {at} TankContent' for at in (SOURCE, *TANKS))
            actual = amount(source, args.fluid), sum(amount(tank, args.fluid) for tank in tanks)
            expected = int(row['source']), int(row['destinations'])
            if actual != expected:
                raise AssertionError(f'Tick {tick}: Horizon {actual}; Java {expected}')
    print(f'{args.fluid.title()} source and combined destinations matched all {len(rows)} Java ticks.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=lambda path: Path(path).resolve(strict=True), default=ROOT / ".local/create.hmod")
    parser.add_argument('--fluid', required=True, choices=('honey', 'tea'))
    run(parser.parse_args())
