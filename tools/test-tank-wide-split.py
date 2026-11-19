#!/usr/bin/env python3
"""Probe Java's immediate post-removal 8,000 mB capacity at an exposed port."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')
mixed = import_module('test-tank-mixed')


def run(args):
    with (ROOT / 'fixtures/tank-wide-split-fill-java.csv').open() as stream:
        expected_rows = list(csv.DictReader(stream))
    lower, upper = ('lava', 'water') if args.reverse else ('water', 'lava')
    with fixture_world(args, 'TankWideSplit', render=False, pack=args.pack, env={'HORIZON_NO_AUDIO': '1'}) as host:
        host.call('command', '/gamemode creative')
        host.call('command', '/item replace entity @s hotbar.0 with minecraft:water_bucket')
        for y in (170, 172):
            for x in range(9, 9 + args.width):
                for z in range(20, 20 + args.width):
                    host.call('command', f'/setblock {x} {y} {z} create:fluid_tank')
        for _ in range(6):
            host.step_to(host.clock() + 1)
        for y, fluid, amount in ((170, lower, 4000), (172, upper, 5000)):
            host.call('command', f'/data merge block 9 {y} 20 {{TankContent:{{Fluid:{{id:"minecraft:{fluid}",amount:{amount}}}}}}}')
        for x in range(9, 9 + args.width):
            for z in range(20, 20 + args.width):
                host.call('command', f'/setblock {x} 171 {z} create:fluid_tank')
        for _ in range(3):
            host.step_to(host.clock() + 1)
        for x in range(9, 9 + args.width):
            for z in range(20, 20 + args.width):
                host.call('command', f'/setblock {x} 171 {z} minecraft:air destroy')
        assert mixed.read(host, 9, 170) == (f'minecraft:{lower}', 4000)
        assert mixed.read(host, 9, 172) == ('minecraft:empty', 0)
        host.call('command', '/setblock 7 170 20 minecraft:stone')
        host.call('command', '/tp @s 7.5 171 20.5')
        mp.until('player positioned', lambda: host.call('state')['player']['position'] == [7.5, 171, 20.5])
        host.call('select', 'minecraft:water_bucket')
        for row in expected_rows:
            host.call('interact', 9, 172, 20, 'west')
            expected = (row['fluid'], int(row['amount']))
            mp.until('bucket reaches tank', lambda: mixed.read(host, 9, 172)[1] >= expected[1])
            actual = mixed.read(host, 9, 172)
            assert actual == expected, (row, actual)
        host.step_to(host.clock() + 1)
        assert mixed.read(host, 9, 172) == ('minecraft:water', 8000)
        host.call('interact', 9, 172, 20, 'west')
        mp.until('regrouped tank accepts another bucket', lambda: mixed.read(host, 9, 172) == ('minecraft:water', 9000))
    print('Immediate upper tank rejected its ninth bucket, then regrouped and accepted it next tick.')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        p.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    p.add_argument('--width', type=int, choices=(2, 3), default=2)
    p.add_argument('--reverse', action='store_true')
    run(p.parse_args())
