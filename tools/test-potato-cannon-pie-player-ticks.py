#!/usr/bin/env python3
"""Compare pie/player attachment on exact authoritative ticks.

The harness summons an ownerless projectile with Java's launch state; actual
player-fired LAN shots are covered separately.
"""
import argparse
import csv
import math
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, install_pack, last_command_message, run_command_harness


def vector(message):
    match = re.search(r'entity data: \[([^\]]+)\]', message)
    assert match, message
    return tuple(float(part.strip().removesuffix('d')) for part in match[1].split(','))


def run(args):
    with (ROOT / 'fixtures/potato-cannon-pie-player-stationary-java.csv').open() as source:
        rows = {int(row['tick']): row for row in csv.DictReader(source)}
    commands = (
        '/gamemode survival @s', '/gamerule naturalRegeneration false',
        '/fill 0 99 -5 16 106 14 minecraft:air',
        '/fill 0 100 -5 16 100 14 minecraft:stone',
        '/setblock 8 101 8 minecraft:stone', '/tp @s 8.0 102 8.5 0 0',
        '/attribute @s minecraft:knockback_resistance base set 1',
        '/summon create:potato_projectile 7.75 102.47 5.0 '
        '{Motion:[0.109862761d,0.0d,2.197255193d],Item:{id:"minecraft:pumpkin_pie",count:1}}',
    )
    operations = [{'op': 'settle'}, *({'op': 'cmd', 'cmd': cmd, 'record': False} for cmd in commands)]
    queries = (
        '/data get entity @s Health', '/data get entity @s Pos',
        '/data get entity @e[type=create:potato_projectile,limit=1] Pos',
        '/data get entity @e[type=create:potato_projectile,limit=1] Motion',
    )
    for _ in range(4):
        operations.append({'op': 'player_loop', 'n': 1})
        operations.extend({'op': 'cmd', 'cmd': query} for query in queries)
    with TemporaryDirectory(prefix='hc-pie-player-ticks-') as scratch:
        game = Path(scratch) / 'game'
        install_pack(game, args.pack)
        records = run_command_harness(args, game, 'pie-player-ticks', operations)
    samples = [last_command_message(record) for record in records if record['cmd'].startswith('/data')]
    assert len(samples) == 16, len(samples)
    for tick in range(1, 5):
        health, player, shot, motion = samples[(tick - 1) * 4:tick * 4]
        value = re.search(r'entity data: ([\d.]+)f$', health)
        assert value and float(value[1]) == float(rows[tick]['health']), (tick, health)
        relative = tuple(a - b for a, b in zip(vector(shot), vector(player), strict=True))
        actual = (*relative, *vector(motion))
        expected = tuple(float(rows[tick][key]) for key in ('x', 'y', 'z', 'vx', 'vy', 'vz'))
        assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(actual, expected, strict=True)), (
            tick, actual, expected)
    print('Ownerless summoned pie matched Java player health, attachment offset and velocity on ticks 1–4.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
