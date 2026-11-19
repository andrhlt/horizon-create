#!/usr/bin/env python3
"""Replay the pinned Java mixed-fluid tank join and separation."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')

def read(host, x, y):
    tag = host.command(f'/data get block {x} {y} 20')
    amount = re.search(r'TankContent: \{Fluid: \{[^}]*amount: (\d+)', tag)
    name = re.search(r'TankContent: \{Fluid: \{[^}]*id: "([^"]+)"', tag)
    return (name[1], int(amount[1])) if name and amount else ('minecraft:empty', 0)

def run(args):
    with (ROOT / 'fixtures/tank-mixed-java.csv').open() as f: rows = list(csv.DictReader(f))
    with fixture_world(args, 'TankMixed', render=False, pack=args.pack) as host:
        host.call('command', '/gamemode creative')
        for slot, item in enumerate(('water_bucket', 'lava_bucket', 'bucket')):
            host.call('command', f'/item replace entity @s hotbar.{slot} with minecraft:{item}')
        for rig in range(2):
            x = 9 + 4 * rig
            for y in (170, 172): host.call('command', f'/setblock {x} {y} 20 create:fluid_tank')
        for _ in range(6): host.step_to(host.clock() + 1)
        for rig in range(2):
            x = 9 + 4 * rig
            for y, name, amount in ((170, ('water', 'lava')[rig], 4000), (172, ('lava', 'water')[rig], 5000)):
                host.call('command', f'/data merge block {x} {y} 20 {{TankContent:{{Fluid:{{id:"minecraft:{name}",amount:{amount}}}}}}}')
        for tick in range(9, 19):
            if tick == 10:
                for x in (9, 13): host.call('command', f'/setblock {x} 171 20 create:fluid_tank')
            if tick == 13:
                for x in (9, 13): host.call('command', f'/setblock {x} 171 20 minecraft:air destroy')
            if tick > 9: host.step_to(host.clock() + 1)
            for rig in range(2):
                x = 9 + 4 * rig
                for row in (r for r in rows if int(r['tick']) == tick and int(r['rig']) == rig):
                    y = int(row['y'])
                    assert host.call('block', x, 170 + y, 20)['block'] == row['block'], (tick, rig, y)
                    if row['block'] == 'minecraft:air': continue
                    root = 171 if tick in (10, 11, 12) and y else 170 + y
                    assert read(host, x, root) == (row['fluid'], int(row['amount'])), (tick, rig, y, read(host, x, root), row)
                    tag = host.command(f'/data get block {x} {root} 20')
                    height = re.search(r'Height: (\d+)', tag)
                    assert height and int(height[1]) * 8000 == int(row['capacity']), (tick, rig, y, tag, row)
            if tick == 12:
                # Exercise every exposed port. Matching buckets add then remove
                # 1,000 mB from the same Java controller.
                for rig in range(2):
                    x = 9 + 4 * rig
                    host.call('command', f'/setblock {x} 169 23 minecraft:stone')
                    host.call('command', f'/tp @s {x + .5} 170 23.5')
                    mp.until('player positioned', lambda: host.call('state')['player']['position'] == [x + .5, 170, 23.5])
                    for y in range(3):
                        name = (('water', 'lava')[rig] if y == 0 else ('lava', 'water')[rig])
                        root, amount = (170, 4000) if y == 0 else (171, 5000)
                        host.call('look-at', x + .5, 170.5 + y, 20.5)
                        mp.until('tank targeted', lambda: (host.call('looking-at').get('block') or {}).get('pos') == [x, 170 + y, 20])
                        for item, expected in ((name + '_bucket', amount + 1000), ('bucket', amount)):
                            host.call('select', f'minecraft:{item}')
                            host.call('mouse', 'right', 'click')
                            mp.until('port changes expected controller', lambda: read(host, x, root) == (f'minecraft:{name}', expected))
                            other = 171 if root == 170 else 170
                            assert read(host, x, other) == (f'minecraft:{("lava", "water")[rig] if root == 170 else ("water", "lava")[rig]}', 5000 if root == 170 else 4000)
    print(f'All {len(rows)} Java mixed-fluid samples and six port interactions matched.')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'): p.add_argument(name, type=Path)
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(p.parse_args())
