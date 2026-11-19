#!/usr/bin/env python3
"""Exercise mixed-fluid tank ports through a LAN guest."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')
mixed = import_module('test-tank-mixed')
GUEST = 'MixedTankGuest'


def run(args):
    with fixture_world(args, 'TankMixedLAN', render=True, pack=args.pack, env={'HORIZON_NO_AUDIO': '1'}) as host:
        for y in (170, 172):
            host.call('command', f'/setblock 9 {y} 20 create:fluid_tank')
        for _ in range(6):
            host.step_to(host.clock() + 1)
        for y, fluid, amount in ((170, 'water', 4000), (172, 'lava', 5000)):
            host.call('command', f'/data merge block 9 {y} 20 {{TankContent:{{Fluid:{{id:"minecraft:{fluid}",amount:{amount}}}}}}}')
        host.call('command', '/setblock 9 171 20 create:fluid_tank')
        for _ in range(2):
            host.step_to(host.clock() + 1)
        port = host.call('lan', 'open', '0', 'commands', 'force')['port']
        with TemporaryDirectory(prefix='hc-tank-mixed-lan-') as scratch, mp.joined_client(
            args, Path(scratch), f'127.0.0.1:{port}', GUEST, render=True,
            scenario='tank-mixed-lan', pack=args.pack, env={'HORIZON_NO_AUDIO': '1'},
        ) as guest:
            mp.until('guest joined', lambda: any(p['name'] == GUEST and p['placed'] for p in host.call('lan', 'status')['guests']))
            for command in (f'/gamemode creative {GUEST}', '/setblock 9 169 23 minecraft:stone',
                            f'/tp {GUEST} 9.5 170 23.5',
                            f'/item replace entity {GUEST} hotbar.0 with minecraft:water_bucket',
                            f'/item replace entity {GUEST} hotbar.1 with minecraft:lava_bucket',
                            f'/item replace entity {GUEST} hotbar.2 with minecraft:bucket'):
                host.call('command', command)
            mp.until('guest positioned', lambda: guest.call('state')['player']['position'] == [9.5, 170, 23.5])
            host.step_to(host.clock() + 1)
            for y in range(3):
                fluid, root, amount = ('water', 170, 4000) if y == 0 else ('lava', 171, 5000)
                guest.call('look-at', 9.5, 170.5 + y, 20.5)
                mp.until('guest targets tank', lambda: (guest.call('looking-at').get('block') or {}).get('pos') == [9, 170 + y, 20])
                for item, expected in ((fluid + '_bucket', amount + 1000), ('bucket', amount)):
                    guest.call('select', f'minecraft:{item}')
                    mp.until('guest selected bucket', lambda: f'id: "minecraft:{item}"' in host.command(f'/data get entity {GUEST} SelectedItem'))
                    guest.call('mouse', 'right', 'click')
                    mp.until('guest interaction reaches expected controller', lambda: mixed.read(host, 9, root) == (f'minecraft:{fluid}', expected))
                    other = 171 if root == 170 else 170
                    assert mixed.read(host, 9, other) == (('minecraft:lava', 5000) if root == 170 else ('minecraft:water', 4000))
            host.call('command', '/setblock 9 171 20 minecraft:air destroy')
            for _ in range(2):
                host.step_to(host.clock() + 1)
            assert mixed.read(host, 9, 170) == ('minecraft:water', 4000)
            assert mixed.read(host, 9, 172) == ('minecraft:lava', 5000)
    print('LAN guest exercised all three mixed-fluid ports; both fluids survived separation.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        p.add_argument(name, type=Path)
    p.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(p.parse_args())
