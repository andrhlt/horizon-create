#!/usr/bin/env python3
"""Compare actual LAN pufferfish hits against a registered Java player.

Live player ticks can move the target between reads; this checks damage,
projectile retention and zero projectile velocity, not exact attachment offset.
"""
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
SHOT = '@e[type=create:potato_projectile,limit=1]'
GUEST = 'PieGuest'


def run(args):
    with (ROOT / 'fixtures/potato-cannon-pufferfish-player-flight-java.csv').open() as source:
        rows = {int(row['tick']): row for row in csv.DictReader(source)}
    direction = 'host-to-guest' if args.host_attacks else 'guest-to-host'
    with TemporaryDirectory(prefix='hc-pie-pvp-') as scratch:
        with fixture_world(args, 'PiePlayer', render=False, pack=args.pack) as host:
            host.commands((
                '/fill 5 100 0 12 100 16 minecraft:stone',
                '/fill 5 101 0 12 106 16 minecraft:air',
                '/setblock 8 101 8 minecraft:stone',
                '/gamerule pvp true', '/gamerule naturalRegeneration false',
            ))
            port = host.call('lan', 'open', '0', 'commands', 'force')['port']
            with multiplayer.joined_client(args, Path(scratch), f'127.0.0.1:{port}', GUEST,
                                           scenario='pie-player-' + direction, pack=args.pack) as guest:
                multiplayer.until('guest to join', lambda: any(
                    player['name'] == GUEST and player['placed']
                    for player in host.call('lan', 'status')['guests']))
                attacker, attacker_name, victim_name = ((host, '@s', GUEST) if args.host_attacks
                                                        else (guest, GUEST, '@s'))
                host.commands((
                    f'/gamemode survival {attacker_name}', f'/gamemode survival {victim_name}',
                    f'/attribute {victim_name} minecraft:knockback_resistance base set 1',
                    f'/tp {attacker_name} 8.5 101 3.5 0 0', f'/tp {victim_name} 8.0 102 8.5 0 0',
                    f'/item replace entity {attacker_name} hotbar.0 with create:potato_cannon',
                    f'/item replace entity {attacker_name} hotbar.1 with minecraft:pufferfish 3',
                ))
                multiplayer.until('cannon and ammo', lambda:
                    attacker.call('inventory')['counts'].get('minecraft:pufferfish') == 3)
                attacker.call('select', '1')
                attacker.call('use-item')
                multiplayer.until('shot fired', lambda:
                    attacker.call('inventory')['counts'].get('minecraft:pufferfish') == 2)
                assert (attacker.call('inventory')['held'] or {}).get('damage', 0) == 1
                start = host.clock()
                for tick in range(1, 3):
                    host.step_to(start + tick)
                    shot = carrot.data(host, SHOT)
                    health_message = host.command(f'/data get entity {victim_name} Health')
                    value = re.search(r'entity data: ([\d.]+)f$', health_message)
                    assert value, health_message
                    health = float(value[1])
                    print(f'{direction} tick {tick}: health={health} shot={shot}', flush=True)
                    if tick >= 2 and health == 16.0:
                        message = host.command(f'/data get entity {victim_name} active_effects')
                        entries = re.findall(r'\{[^{}]*\}', message)
                        effects = {}
                        for entry in entries:
                            name = re.search(r'id:\s*"minecraft:([a-z_]+)"', entry)
                            duration = re.search(r'duration:\s*(\d+)', entry)
                            amplifier = re.search(r'amplifier:\s*(\d+)', entry)
                            if name and duration:
                                effects[name[1]] = (int(duration[1]), int(amplifier[1]) if amplifier else 0)
                        print(f'{direction}: sampled effects={effects}', flush=True)
                        for name, maximum, amp in (('poison', 1200, 1), ('hunger', 300, 2), ('nausea', 300, 0)):
                            assert name in effects and 0 < effects[name][0] <= maximum and effects[name][1] == amp, (tick, effects, message)

                    if tick <= 2:
                        assert health == float(rows[tick]['health']), (tick, health, rows[tick])
                    else:
                        assert float(rows[tick]['health']) <= health <= 20, (tick, health)
                    assert bool(shot) == (rows[tick]['removed'] == 'false'), (tick, shot)
                    if tick >= 2:
                        assert carrot.vector(shot, 'Motion') == (0.0, 0.0, 0.0), (tick, shot)
                        player = carrot.data(host, victim_name)
                        offset = tuple(a - b for a, b in zip(carrot.vector(shot, 'Pos'),
                                                             carrot.vector(player, 'Pos'), strict=True))
                        expected = tuple(float(rows[tick][key]) for key in ('x', 'y', 'z'))
                        carrot.near(offset, expected, f'{direction} tick {tick}')
    print(f'{direction}: player damage and retained pufferfish and player effects matched Java.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--host-attacks', action='store_true')
    os.environ['HORIZON_NO_AUDIO'] = '1'
    run(parser.parse_args())
