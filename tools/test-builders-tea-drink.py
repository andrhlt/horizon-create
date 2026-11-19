#!/usr/bin/env python3
"""Compare Builder's Tea from use-item input to the last effect tick in the trace."""
import argparse
import csv
import re
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, install_pack, last_command_message, run_command_harness

SETUP = (
    '/gamemode survival @s',
    '/gamerule naturalRegeneration false',
    '/item replace entity @s hotbar.0 with create:builders_tea',
)
SAMPLE = (
    '/data get entity @s Inventory[{Slot:0b}].id',
    '/data get entity @s foodLevel',
    '/data get entity @s foodSaturationLevel',
    '/data get entity @s active_effects',
)


def commands(values, *, record=True):
    return ({'op': 'cmd', 'cmd': value, 'record': record} for value in values)


def operations(reference):
    yield from commands(SETUP, record=False)
    yield {'op': 'use_item'}
    for row in reference:
        if row['tick'] != '0':
            yield {'op': 'tick', 'n': 1}
        yield from commands(SAMPLE)


def data(message):
    return message.split('entity data: ', 1)[-1]


def field(message, name, default):
    match = re.search(rf'\b{name}:\s*(\d+)', message)
    return int(match[1]) if match else default


def compare(row, messages):
    item, hunger, saturation, effect = map(data, messages)
    has_haste = 'minecraft:haste' in effect
    found = (item.strip('"'), int(hunger), field(effect, 'duration', 0) if has_haste else 0,
             field(effect, 'amplifier', 0) if has_haste else -1,
             bool(has_haste and field(effect, 'show_particles', 1)),
             bool(has_haste and field(effect, 'show_icon', 1)))
    expected = (row['item'], int(row['hunger']), int(row['haste_duration']),
                int(row['amplifier']), row['particles'] == 'true', row['icon'] == 'true')
    if found != expected or not isclose(float(saturation.rstrip('f')), float(row['saturation']), abs_tol=1e-6):
        raise AssertionError(f"Tick {row['tick']}: Horizon {messages}; Java {row}.")


def run(args):
    with (ROOT / 'fixtures/builders-tea-drink-java.csv').open() as file:
        reference = list(csv.DictReader(file))
    with TemporaryDirectory(prefix='hc-tea-drink-') as scratch:
        game = Path(scratch) / 'game'
        install_pack(game, args.pack)
        records = run_command_harness(args, game, 'builders-tea-drink', operations(reference))
    if len(records) != len(reference) * len(SAMPLE):
        raise AssertionError(f'Expected {len(reference) * len(SAMPLE)} samples, got {len(records)}.')
    for index, row in enumerate(reference):
        start = index * len(SAMPLE)
        compare(row, list(map(last_command_message, records[start:start + len(SAMPLE)])))
    print(f'Matched Java item, saturation, and hidden Haste on all {len(reference)} player ticks.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('ctl', 'client', 'resources'):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    run(parser.parse_args())
