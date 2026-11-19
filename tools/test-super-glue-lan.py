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
    print('LAN guest Super Glue clicks matched the Java region and two durability points.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
