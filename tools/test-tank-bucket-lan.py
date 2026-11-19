#!/usr/bin/env python3
"""Replay Java creative-tank bucket configuration through a LAN guest."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')
GUEST = 'TankGuest'

def run(args):
    rows = [line.split('|') for line in (ROOT / 'fixtures/tank-bucket-java.txt').read_text().splitlines()]
    with fixture_world(args, 'TankBucketLAN', render=True, pack=args.pack, env={'HORIZON_NO_AUDIO': '1'}) as host:
        for cmd in ('/setblock 9 170 20 create:creative_fluid_tank', '/setblock 9 169 23 minecraft:stone'):
            host.call('command', cmd)
        port = host.call('lan', 'open', '0', 'commands', 'force')['port']
        with TemporaryDirectory(prefix='hc-tank-lan-') as scratch, mp.joined_client(
            args, Path(scratch), f'127.0.0.1:{port}', GUEST, render=True,
            scenario='tank-bucket-lan', pack=args.pack, env={'HORIZON_NO_AUDIO': '1'},
        ) as guest:
            mp.until('guest joined', lambda: any(p['name'] == GUEST and p['placed'] for p in host.call('lan', 'status')['guests']))
            for cmd in (f'/gamemode survival {GUEST}', f'/clear {GUEST}',
                        f'/item replace entity {GUEST} hotbar.0 with minecraft:water_bucket',
                        f'/item replace entity {GUEST} hotbar.1 with minecraft:bucket',
                        f'/tp {GUEST} 9.5 170 23.5'):
                host.call('command', cmd)
            mp.until('guest positioned', lambda: guest.call('state')['player']['position'] == [9.5, 170, 23.5])
            host.step_to(host.clock() + 1)
            guest.call('look-at', 9.5, 170.5, 20.5)
            mp.until('guest targets tank', lambda: (guest.call('looking-at').get('block') or {}).get('pos') == [9, 170, 20])
            for held in ('minecraft:water_bucket', 'minecraft:bucket'):
                row = next(row for row in rows if row[0].endswith('true') and row[1:3] == ['SURVIVAL', held])
                if held == 'minecraft:bucket':
                    host.call('command', f'/item replace entity {GUEST} hotbar.0 with minecraft:air')
                guest.call('select', held)
                mp.until('guest selected bucket', lambda: f'id: "{held}"' in host.command(f'/data get entity {GUEST} SelectedItem'))
                guest.call('mouse', 'right', 'click')
                amount, fluid = row[5].split(' ', 1)
                def matched():
                    tag = host.command('/data get block 9 170 20')
                    return tag if (f'id: "{fluid}"' in tag and f'amount: {amount}' in tag if int(amount) else 'TankContent: {Fluid:' not in tag) else None
                mp.until('guest interaction reaches host', matched)
                selected = host.command(f'/data get entity {GUEST} SelectedItem')
                assert f'id: "{held}"' in selected and 'count: 1' in selected, selected
                assert host.call('block', 9, 170, 20)['block'] == 'create:creative_fluid_tank'
                if held == 'minecraft:bucket':
                    mp.until('guest receives water bucket', lambda:
                             'minecraft:water_bucket' in host.command(f'/data get entity {GUEST} Inventory'))
    print('LAN survival guest creative-tank bucket interactions matched Java fluid and inventory results.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'): parser.add_argument(name, type=Path)
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
