#!/usr/bin/env python3
"""Replay Java Fluid Tank bucket interactions for ordinary and creative tanks."""
import argparse
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')


def run(args):
    rows = [line.split('|') for line in (ROOT / 'fixtures/tank-bucket-java.txt').read_text().splitlines()]
    with fixture_world(args, 'TankBucket', render=False, pack=args.pack) as host:
        for cmd in ('/gamemode creative', '/setblock 9 169 23 minecraft:stone',
                    '/tp @s 9.5 170 23.5',
                    '/item replace entity @s hotbar.0 with minecraft:water_bucket',
                    '/item replace entity @s hotbar.1 with minecraft:bucket'):
            host.call('command', cmd)
        mp.until('player positioned', lambda: host.call('state')['player']['position'] == [9.5, 170, 23.5])
        for creative_tank, mode in ((False, 'CREATIVE'), (True, 'CREATIVE'), (True, 'SURVIVAL')):
            block = 'create:creative_fluid_tank' if creative_tank else 'create:fluid_tank'
            host.call('command', '/gamemode creative')
            host.call('command', f'/setblock 9 170 20 {block}')
            host.call('command', f'/gamemode {mode.lower()}')
            host.call('look-at', 9.5, 170.5, 20.5)
            mp.until('tank targeted', lambda: (host.call('looking-at').get('block') or {}).get('pos') == [9, 170, 20])
            for held in ('minecraft:water_bucket', 'minecraft:bucket'):
                if creative_tank and mode == 'SURVIVAL' and held == 'minecraft:bucket':
                    host.call('command', '/item replace entity @s hotbar.0 with minecraft:air')
                row = next(row for row in rows if row[0].endswith(str(creative_tank).lower()) and row[1:3] == [mode, held])
                host.call('select', held)
                mp.until('held bucket selected', lambda: f'id: "{held}"' in host.command('/data get entity @s SelectedItem'))
                host.call('mouse', 'right', 'click')
                amount, fluid = row[5].split(' ', 1)
                def matches():
                    tag = host.command('/data get block 9 170 20')
                    return tag if (f'id: "{fluid}"' in tag and f'amount: {amount}' in tag if int(amount)
                                   else 'TankContent: {Fluid:' not in tag) else None
                mp.until('tank contents match Java', matches)
                assert host.call('block', 9, 170, 20)['block'] == block
                selected = host.command('/data get entity @s SelectedItem')
                assert f'id: "{held}"' in selected and 'count: 1' in selected, (row, selected)
                if creative_tank and mode == 'SURVIVAL' and held == 'minecraft:bucket':
                    mp.until('survival player receives water bucket', lambda:
                             'minecraft:water_bucket' in host.command('/data get entity @s Inventory'))
    print('Tank bucket interactions matched pinned Java fluid amounts and retained the tank blocks.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
