#!/usr/bin/env python3
"""Replay Java's filled two-block Fluid Tank splits, including player mining."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')

def read_fluid(host, x, y):
    tag = host.command(f'/data get block {x} {y} 20')
    amount = re.search(r'TankContent: \{Fluid: \{[^}]*amount: (\d+)', tag)
    name = re.search(r'TankContent: \{Fluid: \{[^}]*id: "([^"]+)"', tag)
    return (name[1], int(amount[1])) if name and amount else ('minecraft:empty', 0)

def sample(host, rig, y):
    x = 9 + 4 * rig
    blocks = [host.call('block', x, 170 + n, 20)['block'] for n in (0, 1)]
    if blocks[y] == 'minecraft:air': return ('minecraft:air', 'minecraft:empty', 0, 0)
    root_y = 170 if blocks[0] == 'create:fluid_tank' else 171
    fluid, amount = read_fluid(host, x, root_y)
    return ('create:fluid_tank', fluid, amount, 8000 * blocks.count('create:fluid_tank'))

def setup(host):
    for x in (9, 13):
        for y in (170, 171): host.call('command', f'/setblock {x} {y} 20 create:fluid_tank')
    for _ in range(6): host.step_to(host.clock() + 1)
    for x in (9, 13):
        host.call('command', f'/data merge block {x} 170 20 {{TankContent:{{Fluid:{{id:"minecraft:water",amount:12000}}}}}}')

def run(args):
    with (ROOT / 'fixtures/tank-split-java.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    with fixture_world(args, 'TankSplit', render=False, pack=args.pack) as host:
        setup(host)
        for tick in range(8, 16):
            if tick == 10:
                host.call('command', '/setblock 9 171 20 minecraft:air destroy')
                host.call('command', '/setblock 13 170 20 minecraft:air destroy')
            if tick > 8: host.step_to(host.clock() + 1)
            for row in (r for r in rows if int(r['tick']) == tick):
                rig, y = int(row['rig']), int(row['y'])
                expected = (row['block'], row['fluid'], int(row['amount']), int(row['capacity']))
                actual = sample(host, rig, y)
                assert actual == expected, (tick, rig, y, expected, actual)
        # Mine each position with a player, exercising the live destruction path.
        setup(host)
        host.call('command', '/gamemode creative')
        for x, y, survivor_y in ((9, 171, 170), (13, 170, 171)):
            host.call('command', f'/setblock {x} 169 23 minecraft:stone')
            host.call('command', f'/tp @s {x + .5} 170 23.5')
            mp.until('player positioned', lambda: host.call('state')['player']['position'] == [x + .5, 170, 23.5])
            host.call('look-at', x + .5, y + .5, 20.5)
            mp.until('tank targeted', lambda: (host.call('looking-at').get('block') or {}).get('pos') == [x, y, 20])
            host.call('mouse', 'left', 'click')
            mp.until('tank part mined', lambda: host.call('block', x, y, 20)['block'] == 'minecraft:air')
            mp.until('surviving tank retains Java fluid', lambda: read_fluid(host, x, survivor_y) == ('minecraft:water', 8000))
    print(f'All {len(rows)} Java split samples matched; player mining retained the same 8000 mB on either survivor.')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'): p.add_argument(name, type=Path)
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(p.parse_args())
