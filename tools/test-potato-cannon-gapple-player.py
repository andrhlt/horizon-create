#!/usr/bin/env python3
"""Compare golden-apple impact on real players with pinned Java's hit handler."""
import argparse
import csv
import os
import re
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

carrot = import_module('test-potato-cannon-carrot')
multiplayer = import_module('test-multiplayer')
GUEST = 'GappleGuest'
SHOT = '@e[type=create:potato_projectile,limit=1]'
AMMO = 'minecraft:golden_apple'


def compare_hit(host, attacker, victim_name, expected, args):
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
    # Regeneration can heal the one point before this live LAN read.
    if not value or not float(expected['health']) <= float(value[1]) <= 20.0:
        raise AssertionError(f"Java impact health {expected['health']}, Horizon {health}.")
    absorption = host.command(f'/data get entity {victim_name} AbsorptionAmount')
    value = re.search(r'entity data: ([\d.]+)f$', absorption)
    assert value, absorption
    print('Horizon target', health, absorption, effects, flush=True)
    if args.baseline:
        assert float(value[1]) == 0 and 'minecraft:absorption' not in effects and 'minecraft:regeneration' not in effects,effects
    else:
        assert float(value[1]) == float(expected['absorption']),(absorption,expected)
        actual = {}
        for entry in re.findall(r'\{[^{}]*\}', effects):
            name = re.search(r'id:\s*"minecraft:([a-z_]+)"', entry)
            duration = re.search(r'duration:\s*(\d+)', entry)
            amplifier = re.search(r'amplifier:\s*(\d+)', entry)
            if name and duration:
                actual[name[1]] = (int(duration[1]), int(amplifier[1]) if amplifier else 0)
        wanted = {name: (int(expected[name + '_duration']), int(expected[name + '_amplifier']))
                  for name in ('regeneration','absorption','resistance','fire_resistance')
                  if int(expected[name + '_duration']) >= 0}
        assert set(actual) == set(wanted), (actual, wanted)
        for name, (duration, amplifier) in actual.items():
            assert 0 < duration <= wanted[name][0] and amplifier == wanted[name][1], (name,actual,wanted)
        print('Actual player hit matched Java absorption and effect levels; durations sampled after live LAN ticks.')



def run(args):
    with (ROOT / 'fixtures/potato-cannon-gapple-player-java.csv').open() as file:
        expected = next(row for row in csv.DictReader(file) if row['case'] == args.case)
    global AMMO
    AMMO = 'minecraft:golden_apple' if args.case == 'golden' else 'minecraft:enchanted_golden_apple'
    direction = 'host-to-guest' if args.host_attacks else 'guest-to-host'
    with TemporaryDirectory(prefix='hc-gapple-player-') as scratch, fixture_world(
            args, f'gapple-player-{direction}', render=False, pack=args.pack) as host:
        host.commands(('/fill 5 100 0 12 100 16 minecraft:stone',
                       '/fill 5 101 0 12 106 16 minecraft:air',
                       '/gamerule pvp true', '/gamerule naturalRegeneration false'))
        port = host.call('lan', 'open', 0, 'commands', 'force')['port']
        with multiplayer.joined_client(args, Path(scratch), f'127.0.0.1:{port}', GUEST,
                                       scenario=f'gapple-player-{direction}', pack=args.pack) as guest:
            multiplayer.until('the target guest to join', lambda: any(
                player['name'] == GUEST and player['placed']
                for player in host.call('lan', 'status')['guests']))
            attacker, attacker_name, victim_name = (host, '@s', GUEST) if args.host_attacks else (guest, GUEST, '@s')
            host.commands((f'/gamemode survival {attacker_name}', f'/gamemode survival {victim_name}',
                           f'/tp {attacker_name} 8.5 101 3.5 0 0', f'/tp {victim_name} 8.0 102 8.5 0 0',
                           f'/item replace entity {attacker_name} hotbar.0 with create:potato_cannon',
                           f'/item replace entity {attacker_name} hotbar.1 with {AMMO} 3'))
            compare_hit(host, attacker, victim_name, expected, args)


if __name__ == '__main__':
    os.environ['HORIZON_NO_AUDIO'] = '1'
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('ctl', 'client', 'resources'):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--host-attacks', action='store_true')
    parser.add_argument('--case', choices=('golden','enchanted'), required=True)
    parser.add_argument('--baseline', action='store_true')
    run(parser.parse_args())
