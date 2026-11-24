#!/usr/bin/env python3
"""Verify a LAN guest's real Super Glue clicks and Java durability."""
import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')


def run(args):
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, 'SuperGlueLAN', pack=args.pack, env={'HORIZON_NO_AUDIO':'1'}))
        port = host.call('lan', 'open', '0', 'commands')['port']
        scratch = Path(sessions.enter_context(TemporaryDirectory(prefix='hc-glue-lan-')))
        guest = sessions.enter_context(mp.joined_client(args, scratch, f'127.0.0.1:{port}', 'GlueGuest',
                         render=True, scenario='super-glue-lan', pack=args.pack, env={'HORIZON_NO_AUDIO':'1'}))
        mp.until('guest joins', lambda: any(p['name'] == 'GlueGuest' and p['placed'] for p in host.call('lan', 'status')['guests']))
        host.commands((
            '/fill 2 169 16 10 169 23 minecraft:stone', '/fill 2 170 16 10 175 23 minecraft:air',
            '/fill 5 170 20 7 170 20 minecraft:stone', '/gamemode survival GlueGuest',
            '/tp GlueGuest 6.5 170 17.5', '/item replace entity GlueGuest hotbar.0 with create:super_glue',
        ))
        mp.until('glue held', lambda: mp.count(guest, 'create:super_glue') == 1)
        for x in (5, 7):
            guest.call('look-at', x + .5, 170.5, 20.5)
            mp.until('stone targeted', lambda: (guest.call('looking-at').get('block') or {}).get('pos') == [x, 170, 20])
            guest.call('mouse', 'right', 'click')
            guest.call('wait', 3)
        item = host.command('/data get entity GlueGuest SelectedItem')
        region = host.command('/data get entity @e[type=minecraft:marker,limit=1]')
        assert '"minecraft:damage": 2' in item and 'create:super_glue_start' not in item, item
        assert 'CreateSuperGlue: 1b' in region and 'From: [-1.5d, 0.0d, -0.5d]' in region and 'To: [1.5d, 1.0d, 0.5d]' in region, region
        host.commands((
            '/fill 2 169 28 10 169 33 minecraft:stone',
            '/fill 2 170 32 10 175 33 minecraft:air',
            '/fill 5 170 32 7 170 32 minecraft:stone',
            '/tp GlueGuest 6.5 170 29.5',
            '/item replace entity GlueGuest hotbar.0 with create:super_glue[minecraft:damage=99]',
            '/item replace entity GlueGuest hotbar.1 with create:super_glue',
        ))
        mp.until('guest has near-broken and spare glue', lambda: mp.count(guest, 'create:super_glue') == 2)
        for x in (5, 7):
            guest.call('look-at', x + .5, 170.5, 32.5)
            mp.until('guest spare-charge target', lambda: (guest.call('looking-at').get('block') or {}).get('pos') == [x, 170, 32])
            guest.call('mouse', 'right', 'click')
            guest.call('wait', 3)
        inventory = host.command('/data get entity GlueGuest Inventory')
        region = host.command('/data get entity @e[type=minecraft:marker,x=6.5,y=170,z=32.5,distance=..2,limit=1]')
        print('LAN_SPARE_GLUE_INVENTORY', inventory, flush=True)
        assert 'Slot: 0b' not in inventory, inventory
        assert 'Slot: 1b' in inventory and 'minecraft:damage": 1' in inventory, inventory
        assert 'CreateSuperGlue: 1b' in region, region
        guest.call('key', '2', 'tap')
        mp.until('guest holding spare glue for removal', lambda: 'create:super_glue' in host.command('/data get entity GlueGuest SelectedItem'))
        guest.call('look-at', 5.5, 170.5, 32.5)
        mp.until('guest glued block targeted for removal', lambda: (guest.call('looking-at').get('block') or {}).get('pos') == [5, 170, 32])
        guest.call('mouse', 'left', 'click')
        guest.call('wait', 3)
        removed = host.command('/data get entity @e[type=minecraft:marker,x=6.5,y=170,z=32.5,distance=..2,limit=1]')
        block = host.call('block', 5, 170, 32)['block']
        assert 'No entity was found' in removed, removed
        assert block == 'minecraft:stone', block
    print('LAN guest Super Glue region, charge consumption, and glue removal matched.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
