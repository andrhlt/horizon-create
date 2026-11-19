#!/usr/bin/env python3
"""Compare glistering-melon impact on real players with pinned Java's hit handler."""
import argparse
import csv
import re
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

carrot = import_module('test-potato-cannon-carrot')
multiplayer = import_module('test-multiplayer')
GUEST = 'GlisterGuest'
SHOT = '@e[type=create:potato_projectile,limit=1]'
AMMO = 'minecraft:glistering_melon_slice'


def compare_hit(host, attacker, victim_name, expected):
    multiplayer.until('cannon and ammo', lambda: attacker.call('inventory')['counts'].get(AMMO) == 3)
    attacker.call('select', '1')
    attacker.call('use-item')
    remaining = int(expected['ammo'])
    multiplayer.until('the cannon to fire', lambda: attacker.call('inventory')['counts'].get(AMMO) == remaining)
    held = attacker.call('inventory')['held']
    if held.get('damage', 0) != int(expected['damage']):
        raise AssertionError(f'Unexpected cannon wear: {held}')

    for _ in range(3):
        if carrot.data(host, SHOT) is None:
            break
        host.step_to(host.clock() + 1)
    if carrot.data(host, SHOT) is not None:
        raise AssertionError('The projectile remained after the hit.')

    health, effects = host.commands(f'/data get entity {victim_name} {path}'
                                    for path in ('Health', 'active_effects'))
    value = re.search(r'entity data: ([\d.]+)f$', health)
    if not value or float(value[1]) != float(expected['health']):
        raise AssertionError(f"Java target health {expected['health']}, Horizon {health}.")
    duration = re.search(r'duration:\s*(\d+)', effects)
    amplifier = re.search(r'amplifier:\s*(\d+)', effects)
    if ('minecraft:glowing' not in effects or not duration
            or not 0 < int(duration[1]) <= int(expected['duration'])
            or (int(amplifier[1]) if amplifier else 0) != int(expected['amplifier'])):
        raise AssertionError(f'Unexpected target effects: {effects}.')
    print(f'Actual player hit matched Java damage and Glowing; sampled {duration[1]} ticks remaining.')


def run(args):
    with (ROOT / 'fixtures/potato-cannon-glister-player-java.csv').open() as file:
        expected = next(csv.DictReader(file))
    direction = 'host-to-guest' if args.host_attacks else 'guest-to-host'
    with TemporaryDirectory(prefix='hc-glister-player-') as scratch, fixture_world(
            args, f'glister-player-{direction}', render=False, pack=args.pack) as host:
        host.commands(('/fill 5 100 0 12 100 16 minecraft:stone',
                       '/fill 5 101 0 12 106 16 minecraft:air',
                       '/gamerule pvp true', '/gamerule naturalRegeneration false'))
        port = host.call('lan', 'open', 0, 'commands', 'force')['port']
        with multiplayer.joined_client(args, Path(scratch), f'127.0.0.1:{port}', GUEST,
                                       scenario=f'glister-player-{direction}', pack=args.pack) as guest:
            multiplayer.until('the target guest to join', lambda: any(
                player['name'] == GUEST and player['placed']
                for player in host.call('lan', 'status')['guests']))
            attacker, attacker_name, victim_name = (host, '@s', GUEST) if args.host_attacks else (guest, GUEST, '@s')
            host.commands((f'/gamemode survival {attacker_name}', f'/gamemode survival {victim_name}',
                           f'/tp {attacker_name} 8.5 101 3.5 0 0', f'/tp {victim_name} 8.0 102 8.5 0 0',
                           f'/item replace entity {attacker_name} hotbar.0 with create:potato_cannon',
                           f'/item replace entity {attacker_name} hotbar.1 with {AMMO} 3'))
            compare_hit(host, attacker, victim_name, expected)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('ctl', 'client', 'resources'):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--host-attacks', action='store_true')
    run(parser.parse_args())
