#!/usr/bin/env python3
"""Check a bucket against Java's joined tank before the next world tick."""
import argparse
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')
mixed = import_module('test-tank-mixed')


def run(args):
    with fixture_world(args, 'TankWideImmediate', render=False, pack=args.pack, env={'HORIZON_NO_AUDIO': '1'}) as host:
        host.call('command', '/gamemode creative')
        host.call('command', '/item replace entity @s hotbar.0 with minecraft:lava_bucket')
        host.call('command', '/item replace entity @s hotbar.1 with create:fluid_tank')
        host.call('command', '/setblock 7 169 20 minecraft:stone')
        host.call('command', '/tp @s 7.5 170 20.5')
        mp.until('player positioned', lambda: host.call('state')['player']['position'] == [7.5, 170, 20.5])
        for y in (170, 172):
            for x in (9, 10):
                for z in (20, 21):
                    host.call('command', f'/setblock {x} {y} {z} create:fluid_tank')
        for _ in range(6):
            host.step_to(host.clock() + 1)
        for y, fluid, amount in ((170, 'water', 4000), (172, 'lava', 5000)):
            host.call('command', f'/data merge block 9 {y} 20 {{TankContent:{{Fluid:{{id:"minecraft:{fluid}",amount:{amount}}}}}}}')
        for x in (9, 10):
            for z in (20, 21):
                if not args.player or (x, z) != (10, 21):
                    host.call('command', f'/setblock {x} 171 {z} create:fluid_tank')
        if args.player:
            host.call('command', '/setblock 12 169 21 minecraft:stone')
            host.call('command', '/tp @s 12.5 170 21.5')
            mp.until('player positioned to place', lambda: host.call('state')['player']['position'] == [12.5, 170, 21.5])
            host.call('select', 'create:fluid_tank')
            host.call('interact', 9, 171, 21, 'east')
            assert host.call('block', 10, 171, 21)['block'] == 'create:fluid_tank'
            host.call('command', '/tp @s 7.5 170 20.5')
            mp.until('player positioned to fill', lambda: host.call('state')['player']['position'] == [7.5, 170, 20.5])
        host.call('select', 'minecraft:lava_bucket')
        host.call('interact', 9, 171, 20, 'west')
        mp.until('bucket reaches joined tank', lambda: mixed.read(host, 9, 171)[1] > 0)
        actual = mixed.read(host, 9, 171)
        assert actual == ('minecraft:lava', 6000), ('Java immediate joined controller after bucket', actual)
    print('Immediate join preserved 5,000 mB and accepted a bucket through the middle port.')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        p.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    p.add_argument('--player', action='store_true')
    run(p.parse_args())
