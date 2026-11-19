#!/usr/bin/env python3
"""Compare cannon cooldown using server-owner packets and exact player ticks.

This uses the command harness's integrated server owner; it does not replace
external LAN guest input coverage.
"""
import argparse
import csv
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, install_pack, last_command_message, run_command_harness


def run(args):
    with (ROOT / 'fixtures/potato-cannon-gapple-refire-java.csv').open() as source:
        rows = [row for row in csv.DictReader(source) if row['case'] == args.case]
    ammo = ('minecraft:golden_apple' if args.case == 'golden'
            else 'minecraft:enchanted_golden_apple')
    commands = (
        '/gamemode survival @s',
        '/item replace entity @s hotbar.0 with create:potato_cannon',
        f'/item replace entity @s hotbar.1 with {ammo} 3',
    )
    operations = [
        {'op': 'settle'},
        *({'op': 'cmd', 'cmd': command, 'record': False} for command in commands),
        {'op': 'use_item'},
        {'op': 'cmd', 'cmd': '/data get entity @s Inventory'},
    ]
    for _ in range(1, len(rows)):
        operations.extend((
            {'op': 'player_loop', 'n': 1},
            {'op': 'use_item'},
            {'op': 'cmd', 'cmd': '/data get entity @s Inventory'},
        ))
    with TemporaryDirectory(prefix='hc-gapple-auth-') as scratch:
        game = Path(scratch) / 'game'
        install_pack(game, args.pack)
        records = run_command_harness(args, game, 'gapple-authority-' + args.case, operations)
    inventory = [last_command_message(record) for record in records
                 if record['cmd'] == '/data get entity @s Inventory']
    assert len(inventory) == len(rows), (len(inventory), len(rows))
    for row, text in zip(rows, inventory, strict=True):
        pattern = r'count:\s*(\d+),\s*Slot:\s*1b,\s*id:\s*"' + re.escape(ammo) + '"'
        ammo_count = re.search(pattern, text)
        damage = re.search(r'"minecraft:damage":\s*(\d+)', text)
        assert ammo_count and damage, (row, text)
        actual = (int(ammo_count[1]), int(damage[1]))
        expected = (int(row['inventory_count']), int(row['damage']))
        assert actual == expected, (row, actual, expected)
    print(f'{args.case}: server-owner packet and inventory matched Java on {len(rows)} exact player ticks.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--case', choices=('golden', 'enchanted'), default='enchanted')
    run(parser.parse_args())
