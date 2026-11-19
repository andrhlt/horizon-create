#!/usr/bin/env python3
"""Exercise a LAN guest's initial Minecart Coupling selection on the host."""
import argparse
import csv
import re
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
            '/fill 4 169 20 24 169 28 minecraft:stone',
            '/fill 4 170 24 24 170 24 minecraft:rail[shape=east_west]',
            '/summon minecraft:minecart 8.5 170.0625 24.5 {UUID:[I;0,0,0,1],Motion:[0.1d,0.0d,0.0d],Tags:["coupling_a"]}',
            '/summon minecraft:minecart 11.5 170.0625 24.5 {UUID:[I;0,0,0,2],Tags:["coupling_b"]}',
            '/summon minecraft:minecart 14.5 170.0625 24.5 {UUID:[I;0,0,0,3],Tags:["coupling_c"]}',
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
            for tag, last in (('coupling_a', 1), ('coupling_b', 2), ('coupling_c', 3)):
                uuid = host.command(f'/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID')
                if f'[I; 0, 0, 0, {last}]' not in uuid: raise RuntimeError(f'Wrong {tag} UUID: {uuid}')
            guest.call('select', 'create:minecart_coupling')
            for x in (8.5, 11.5, 11.5, 14.5): click(x)
            multiplayer.until('two guest links', lambda: multiplayer.count(guest, 'create:minecart_coupling') == 1)
            if 'Count: 2' not in host.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]'):
                raise RuntimeError('Host did not create the two-link chain')
            with (Path(__file__).resolve().parents[1] / 'fixtures/minecart-coupling-chain-motion-java.csv').open(newline='') as stream: expected = list(csv.DictReader(stream))
            for row in expected:
                actual = []
                for tag in ('coupling_a', 'coupling_b', 'coupling_c'):
                    data = host.command(f'/data get entity @e[type=minecraft:minecart,tag={tag},limit=1]')
                    actual.extend(float(re.search(key + r': \[([-0-9.eE]+)d', data).group(1)) for key in ('Pos', 'Motion'))
                target = [float(row[key]) for key in ('a_x', 'a_velocity', 'b_x', 'b_velocity', 'c_x', 'c_velocity')]
                if any(abs(a-b) > 0.00001 for a,b in zip(actual, target)): raise RuntimeError(f"Host motion tick {row['tick']}: {actual} vs {target}")
                if int(row['tick']) != len(expected)-1: host.step_to(host.clock()+1)
    print('LAN guest-created chain matched 21 Java motion ticks on the host.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'): parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument('--pack', type=lambda value: Path(value).resolve(strict=True))
    with TemporaryDirectory(prefix='hc-coupling-guest-') as scratch: run(parser.parse_args(), Path(scratch))
