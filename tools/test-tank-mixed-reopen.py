#!/usr/bin/env python3
"""Check mixed-fluid column storage after a cold Horizon world reopen.

Java's serialized controller fluid, height and upper-part controller identity
are the reference. Java's server restart timing is not sampled here.
"""
import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')
mixed = import_module('test-tank-mixed')


def check_controllers(host, rig):
    x = 9 + 4 * rig
    with (ROOT / 'fixtures/tank-mixed-save-java.csv').open() as stream:
        rows = [row for row in csv.DictReader(stream) if int(row['rig']) == rig]
    for row in rows:
        y = 170 + int(row['y'])
        tag = host.command(f'/data get block {x} {y} 20')
        assert mixed.read(host, x, y) == (row['fluid'], int(row['amount'])), tag
        if row['height']:
            size = re.search(r'Size: (\d+)', tag)
            height = re.search(r'Height: (\d+)', tag)
            assert size and size[1] == row['size'] and height and height[1] == row['height'], tag
    for y in range(170, 173):
        assert host.call('block', x, y, 20)['block'] == 'create:fluid_tank'


def check_ports(host, rig):
    x = 9 + 4 * rig
    host.call('command', f'/setblock {x} 169 23 minecraft:stone')
    host.call('command', f'/tp @s {x + .5} 170 23.5')
    mp.until('player positioned', lambda: host.call('state')['player']['position'] == [x + .5, 170, 23.5])
    for y in range(3):
        fluid = (('water', 'lava')[rig] if y == 0 else ('lava', 'water')[rig])
        root, amount = (170, 4000) if y == 0 else (171, 5000)
        host.call('look-at', x + .5, 170.5 + y, 20.5)
        mp.until('tank targeted', lambda: (host.call('looking-at').get('block') or {}).get('pos') == [x, 170 + y, 20])
        for item, expected in ((fluid + '_bucket', amount + 1000), ('bucket', amount)):
            host.call('select', f'minecraft:{item}')
            host.call('mouse', 'right', 'click')
            mp.until('port changes expected controller', lambda: mixed.read(host, x, root) == (f'minecraft:{fluid}', expected))
        check_controllers(host, rig)


def run(args):
    with fixture_world(args, 'TankMixedReopen', render=False, pack=args.pack, env={'HORIZON_NO_AUDIO': '1'}) as host:
        host.call('command', '/gamemode creative')
        for slot, item in enumerate(('water_bucket', 'lava_bucket', 'bucket')):
            host.call('command', f'/item replace entity @s hotbar.{slot} with minecraft:{item}')
        for x in (9, 13):
            for y in (170, 172):
                host.call('command', f'/setblock {x} {y} 20 create:fluid_tank')
        for _ in range(6):
            host.step_to(host.clock() + 1)
        for rig in range(2):
            x = 9 + 4 * rig
            for y, fluid, amount in ((170, ('water', 'lava')[rig], 4000), (172, ('lava', 'water')[rig], 5000)):
                host.call('command', f'/data merge block {x} {y} 20 {{TankContent:{{Fluid:{{id:"minecraft:{fluid}",amount:{amount}}}}}}}')
            host.call('command', f'/setblock {x} 171 20 create:fluid_tank')
        for _ in range(3):
            host.step_to(host.clock() + 1)
        for rig in range(2):
            check_controllers(host, rig)
        host.restart()
        # The launch can advance ticks before the fixture freezes the world.
        for _ in range(6):
            for rig in range(2):
                check_controllers(host, rig)
            host.step_to(host.clock() + 1)
        for rig in range(2):
            check_ports(host, rig)
    print('Both mixed-fluid orders retained their controllers and all six ports after cold reopen and six subsequent ticks.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        p.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(p.parse_args())
