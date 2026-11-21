#!/usr/bin/env python3
"""Verify a LAN guest can open Ponder without changing shared gameplay state."""
import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import tempfile
from fixture_world import ROOT

mp = import_module('test-multiplayer')


def open_ponder(client, name):
    client.call('key', 'e', 'tap')
    mp.until(f'{name} inventory open', lambda: client.call('screen')['screen'] == 'inventory')
    client.call('wait', 3)
    button = client.call('screen')['recipe_book']['targets'][0]
    left, top = button[0] - 104, button[1] - 61
    client.call('scroll-at', left + 16, top + 150, 0)
    client.call('wait', 3)
    client.call('key', 'w', 'down')
    try:
        mp.until(f'{name} Ponder opens', lambda: client.call('screen')['screen'] == 'mod')
    finally:
        client.call('key', 'w', 'up')


def run(args):
    with tempfile.TemporaryDirectory(prefix='hc-ponder-guest-') as tmp:
        scratch = Path(tmp)
        with mp.dedicated(
                args, scratch, scenario='PonderGuest', pack=args.pack,
                artifact_dir=scratch) as (address, command):
            with ExitStack() as clients:
                host = clients.enter_context(mp.joined_client(
                    args, scratch, address, 'PonderHost', render=True,
                    scenario='PonderGuest', pack=args.pack, artifact_dir=scratch))
                guest = clients.enter_context(mp.joined_client(
                    args, scratch, address, 'PonderGuest', render=True,
                    scenario='PonderGuest', pack=args.pack, artifact_dir=scratch))
                command('setblock 5 170 20 minecraft:diamond_block')
                mp.until('host sees world marker', lambda: host.call('block', 5, 170, 20)['state'].startswith('minecraft:diamond_block'))
                mp.until('guest sees world marker', lambda: guest.call('block', 5, 170, 20)['state'].startswith('minecraft:diamond_block'))
                command('gamemode survival PonderHost')
                command('gamemode survival PonderGuest')
                command('give PonderHost create:shaft 1')
                command('give PonderGuest create:shaft 1')
                mp.until('host receives Shaft', lambda: mp.count(host, 'create:shaft') == 1)
                mp.until('guest receives Shaft', lambda: mp.count(guest, 'create:shaft') == 1)

                host_before = host.call('inventory')['counts']
                guest_before = guest.call('inventory')['counts']
                open_ponder(guest, 'guest')
                guest.call('key', 'backspace', 'tap')
                mp.until('guest returns to inventory', lambda: guest.call('screen')['screen'] == 'inventory')
                assert guest.call('inventory')['counts'] == guest_before
                guest.call('key', 'e', 'tap')
                mp.until('guest returns to gameplay', lambda: guest.call('screen')['screen'] == 'playing')
                open_ponder(host, 'host')
                host.call('key', 'backspace', 'tap')
                mp.until('host returns to inventory', lambda: host.call('screen')['screen'] == 'inventory')
                assert host.call('inventory')['counts'] == host_before
                host.call('key', 'e', 'tap')
                mp.until('host returns to gameplay', lambda: host.call('screen')['screen'] == 'playing')
                assert host.call('inventory')['counts'] == host_before
                assert guest.call('inventory')['counts'] == guest_before

        with mp.dedicated(
                args, scratch, scenario='PonderGuestReload', pack=args.pack,
                artifact_dir=scratch) as (address, _command):
            with ExitStack() as clients:
                host = clients.enter_context(mp.joined_client(
                    args, scratch, address, 'PonderHost', render=True,
                    scenario='PonderGuestReload', pack=args.pack, artifact_dir=scratch))
                guest = clients.enter_context(mp.joined_client(
                    args, scratch, address, 'PonderGuest', render=True,
                    scenario='PonderGuestReload', pack=args.pack, artifact_dir=scratch))
                mp.until('host inventory after save/reopen', lambda: mp.count(host, 'create:shaft') == 1)
                mp.until('guest inventory after save/reopen', lambda: mp.count(guest, 'create:shaft') == 1)
                assert host.call('block', 5, 170, 20)['state'].startswith('minecraft:diamond_block')
                assert guest.call('block', 5, 170, 20)['state'].startswith('minecraft:diamond_block')
    print('LAN host and guest opened Ponder; inventories and world state survived server save/reopen.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument('--pack', type=lambda value: Path(value).resolve(), default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
