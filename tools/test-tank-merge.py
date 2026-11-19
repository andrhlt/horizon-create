#!/usr/bin/env python3
"""Replay the Java merge of independently filled vertical Fluid Tanks."""
import argparse
import csv
from pathlib import Path
import re
from fixture_world import ROOT, fixture_world

def data(host, y):
    return host.command(f'/data get block 9 {y} 20')

def fluid(tag):
    amount = re.search(r'TankContent: \{Fluid: \{[^}]*amount: (\d+)', tag)
    name = re.search(r'TankContent: \{Fluid: \{[^}]*id: "([^"]+)"', tag)
    return (name[1], int(amount[1])) if name and amount else ('minecraft:empty', 0)

def sample(host, y):
    blocks = [host.call('block', 9, 170 + n, 20)['block'] for n in range(3)]
    if blocks[y] == 'minecraft:air': return ('minecraft:air', 'minecraft:empty', 0, 0)
    grouped = all(block == 'create:fluid_tank' for block in blocks)
    name, amount = fluid(data(host, 170 if grouped else 170 + y))
    return ('create:fluid_tank', name, amount, 24000 if grouped else 8000)

def run(args):
    with (ROOT / 'fixtures/tank-merge-java.csv').open() as f: rows = list(csv.DictReader(f))
    with fixture_world(args, 'TankMerge', render=False, pack=args.pack) as host:
        for y in (170, 172): host.call('command', f'/setblock 9 {y} 20 create:fluid_tank')
        for _ in range(6): host.step_to(host.clock() + 1)
        for y, amount in ((170, 4000), (172, 5000)):
            host.call('command', f'/data merge block 9 {y} 20 ' + '{TankContent:{Fluid:{id:"minecraft:water",amount:' + str(amount) + '}}}')
        for tick in range(8, 17):
            if tick == 10: host.call('command', '/setblock 9 171 20 create:fluid_tank')
            if tick > 8: host.step_to(host.clock() + 1)
            for row in (r for r in rows if int(r['tick']) == tick):
                y = int(row['y'])
                expected = (row['block'], row['fluid'], int(row['amount']), int(row['capacity']))
                actual = sample(host, y)
                assert actual == expected, (tick, y, expected, actual)
            if tick >= 10:
                assert fluid(data(host, 172)) == ('minecraft:empty', 0), data(host, 172)
    print(f'All {len(rows)} Java merge samples matched; controller held 9000 mB without duplication.')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'): p.add_argument(name, type=Path)
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(p.parse_args())
