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
            '/fill 4 169 20 16 169 28 minecraft:stone',
            '/setblock 8 170 24 minecraft:rail[shape=north_south]',
            '/setblock 11 170 24 minecraft:rail[shape=north_south]',
            '/summon minecraft:minecart 8.5 170.0625 24.5 {Tags:["coupling_a"]}',
            '/summon minecraft:minecart 11.5 170.0625 24.5 {Tags:["coupling_b"]}',
        ))
        network = host.call('lan', 'open', '0', 'commands', 'force')
        with multiplayer.joined_client(args, scratch, f"127.0.0.1:{network['port']}", GUEST, render=True, scenario='multiplayer-minecart-coupling', pack=args.pack) as guest:
            multiplayer.until('guest to join', lambda: any(p['name'] == GUEST and p['placed'] for p in host.call('lan', 'status')['guests']))
            host.commands((f'/gamemode survival {GUEST}', f'/item replace entity {GUEST} hotbar.0 with create:minecart_coupling 2', f'/item replace entity {GUEST} hotbar.1 with create:wrench', f'/tp {GUEST} 8.5 170 22.5'))
            multiplayer.until('guest to hold couplings', lambda: multiplayer.count(guest, 'create:minecart_coupling') == 2)
            def click(x):
                host.command(f'/tp {GUEST} {x} 170 22.5')
                multiplayer.until('guest to reach cart', lambda: guest.call('state')['player']['position'] == [x, 170.0, 22.5])
                guest.call('look-at', x, 170.2, 24.5)
                guest.call('wait', 4)
                guest.call('mouse', 'right', 'click')
                guest.call('wait', 3)
            carts = [host.command(f'/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID') for tag in ('coupling_a', 'coupling_b')]
            uuids = [re.search(r'\[I;[^]]+\]', cart).group() for cart in carts]
            guest.call('select', 'create:minecart_coupling')
            click(8.5)
            if multiplayer.count(guest, 'create:minecart_coupling') != 2: raise RuntimeError('First selection consumed a coupling')
            click(11.5)
            multiplayer.until('host to consume coupling', lambda: multiplayer.count(guest, 'create:minecart_coupling') == 1)
            link = host.command('/data get entity @e[type=minecraft:marker,tag=create_minecart_coupling,limit=1] CreateMinecartCoupling')
            if 'Length: 3.0f' not in link or not all(uuid in link for uuid in uuids): raise RuntimeError(f'Host did not create the correct pair: {link}; {uuids}')
            guest.call('select', 'create:wrench')
            click(8.5)
            multiplayer.until('guest refund', lambda: multiplayer.count(guest, 'create:minecart_coupling') == 2)
            if 'Test passed' in host.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]'): raise RuntimeError('Host retained removed coupling')
    print('LAN guest created and removed a three-block pair on the host.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'): parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument('--pack', type=lambda value: Path(value).resolve(strict=True))
    with TemporaryDirectory(prefix='hc-coupling-guest-') as scratch: run(parser.parse_args(), Path(scratch))
