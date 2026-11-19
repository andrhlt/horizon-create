#!/usr/bin/env python3
"""Compare authoritative player effect ticks after an ownerless projectile hit."""
import argparse
import csv
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, install_pack, last_command_message, run_command_harness

SETUP = (
    '/gamemode survival @s',
    '/gamerule naturalRegeneration false',
    '/fill 0 99 -5 16 106 10 minecraft:air',
    '/fill 0 100 -5 16 100 10 minecraft:stone',
    '/tp @s 8.5 101 4.5 0 0',
    '/summon create:potato_projectile 8.5 102.4 2.0 '
    '{Motion:[0.0d,0.0d,1.0d],Item:{id:"minecraft:pufferfish",count:1}}',
)
SAMPLE = ('/data get entity @s Health', '/data get entity @s active_effects')


def operations(sample_count):
    yield {'op': 'settle'}
    for command in SETUP:
        yield {'op': 'cmd', 'cmd': command, 'record': False}
    for _ in range(sample_count):
        yield {'op': 'tick', 'n': 1}
        for command in SAMPLE:
            yield {'op': 'cmd', 'cmd': command}


def compare(row, health, effects):
    hp = re.search(r'entity data: ([\d.]+)f$', health)
    entries = re.findall(r'\{[^{}]*\}', effects)
    actual_effects = {}
    for entry in entries:
        name = re.search(r'id:\s*"minecraft:([a-z_]+)"', entry)
        duration = re.search(r'duration:\s*(\d+)', entry)
        amplifier = re.search(r'amplifier:\s*(\d+)', entry)
        if name and duration:
            actual_effects[name[1]] = (int(duration[1]), int(amplifier[1]) if amplifier else 0)
    expected_effects = {name: (int(row[name + '_duration']), int(row[name + '_amplifier']))
                        for name in ('poison', 'hunger', 'nausea')}
    assert hp and float(hp[1]) == float(row['health']), (row, health)
    assert actual_effects == expected_effects, (row, actual_effects, effects)



def run(args):
    with (ROOT / 'fixtures/potato-cannon-pufferfish-player-ticks-java.csv').open() as file:
        reference = list(csv.DictReader(file))
    with TemporaryDirectory(prefix='hc-honey-player-ticks-') as scratch:
        game = Path(scratch) / 'game'
        install_pack(game, args.pack)
        records = run_command_harness(args, game, 'honey-player-ticks', operations(len(reference) + 1))
    messages = list(map(last_command_message, records))
    samples = list(zip(messages[::2], messages[1::2], strict=True))
    if not samples[0][0].endswith('20.0f') or 'minecraft:poison' in samples[0][1]:
        raise AssertionError(f'Unexpected first, pre-hit sample: {samples[0]}.')
    for row, (health, effects) in zip(reference, samples[1:], strict=True):
        compare(row, health, effects)
    print(f'Summoned pufferfish projectile matched Java player health and three pufferfish effects on {len(reference)} ticks.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('ctl', 'client', 'resources'):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    run(parser.parse_args())
