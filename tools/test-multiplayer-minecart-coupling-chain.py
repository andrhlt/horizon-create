#!/usr/bin/env python3
"""Exercise a LAN guest's initial Minecart Coupling selection on the host."""
import argparse
import importlib.util
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import fixture_world

spec = importlib.util.spec_from_file_location('multiplayer', Path(__file__).with_name('test-multiplayer.py'))
multiplayer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multiplayer)
GUEST = 'CouplingGuest'

def run(args, scratch):
    with fixture_world(args, 'MinecartCouplingGuest', pack=args.pack) as host:
        host.commands((
            '/fill 4 169 20 18 169 28 minecraft:stone',
            '/setblock 8 170 24 minecraft:rail[shape=north_south]',
            '/setblock 11 170 24 minecraft:rail[shape=north_south]',
            '/summon minecraft:minecart 8.5 170.0625 24.5 {Tags:["coupling_a"]}',
            '/summon minecraft:minecart 11.5 170.0625 24.5 {Tags:["coupling_b"]}',
            '/setblock 14 170 24 minecraft:rail[shape=north_south]',
            '/summon minecraft:minecart 14.5 170.0625 24.5 {Tags:["coupling_c"]}',
        ))
        network = host.call('lan', 'open', '0', 'commands', 'force')
        with multiplayer.joined_client(args, scratch, f"127.0.0.1:{network['port']}", GUEST, render=True, scenario='multiplayer-minecart-coupling', pack=args.pack) as guest:
            multiplayer.until('guest to join', lambda: any(p['name'] == GUEST and p['placed'] for p in host.call('lan', 'status')['guests']))
            host.commands((f'/gamemode survival {GUEST}', f'/item replace entity {GUEST} hotbar.0 with create:minecart_coupling 3', f'/item replace entity {GUEST} hotbar.1 with create:wrench', f'/tp {GUEST} 8.5 170 22.5'))
            multiplayer.until('guest to hold couplings', lambda: multiplayer.count(guest, 'create:minecart_coupling') == 3)
            def click(x):
                host.command(f'/tp {GUEST} {x} 170 22.5')
                multiplayer.until('guest to reach cart', lambda: guest.call('state')['player']['position'] == [x, 170.0, 22.5])
                guest.call('look-at', x, 170.2, 24.5)
                guest.call('wait', 4)
                guest.call('mouse', 'right', 'click')
                guest.call('wait', 3)
            guest.call('select', 'create:minecart_coupling')
            for x in (8.5, 11.5, 11.5, 14.5): click(x)
            multiplayer.until('two guest links', lambda: multiplayer.count(guest, 'create:minecart_coupling') == 1)
            if 'Count: 2' not in host.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]'):
                raise RuntimeError('Host did not create the two-link chain')
            for x in (14.5, 8.5): click(x)
            if multiplayer.count(guest, 'create:minecart_coupling') != 1 or 'Count: 2' not in host.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]'):
                raise RuntimeError('Closing loop consumed an item or created a link')
            guest.call('select', 'create:wrench'); click(11.5)
            multiplayer.until('both coupling refunds', lambda: multiplayer.count(guest, 'create:minecart_coupling') == 3)
            if 'Test passed' in host.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]'):
                raise RuntimeError('Host retained a middle-cart link')
    print('LAN guest created and removed a two-link chain; closing loop was rejected.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'): parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument('--pack', type=lambda value: Path(value).resolve(strict=True))
    with TemporaryDirectory(prefix='hc-coupling-guest-') as scratch: run(parser.parse_args(), Path(scratch))
