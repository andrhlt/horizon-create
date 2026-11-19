#!/usr/bin/env python3
"""Compare Java with held-stack replacement during actual LAN guest food use.

The host's command supplies a new count-two stack. The replacement boundary is
read from consecutive authoritative guest player ticks, not world time. For a
different food we sample through the expected cancellation tick; for the same
food we sample through the original consumption tick.
"""
import argparse
import csv
from importlib import import_module
from food_trace import same_f32
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

food_test = import_module('test-food-use-lan')
mp = import_module('test-multiplayer')
GUEST = food_test.GUEST
FOODS = food_test.FOODS


def guest_rows(trace, offset):
    return [row for row in food_test.trace_rows(trace)[offset:] if row['player'] == GUEST]


def compare(food, scenario, rows, references):
    start = next(i for i, r in enumerate(rows) if r['using'] == 0 and r['slot0_item'] == f'create:{food}')
    rows = rows[start:]
    boundary = next(i for i, r in enumerate(rows) if r['slot0_count'] == 2)
    if not 1 <= boundary < 32:
        raise AssertionError(f'{food} {scenario}: replacement at tick {boundary}')
    # A held button can start another use in the consumption tick. Java's
    # explicit same_repeat scenario models that additional actual use input.
    java_scenario = 'same_repeat' if scenario == 'same' and len(rows) > 32 and rows[32]['using'] == 0 else scenario
    expected = [r for r in references if r['food'] == food and r['scenario'] == java_scenario and int(r['boundary']) == boundary]
    if len(expected) != 38:
        raise AssertionError('Java reference incomplete')
    end = boundary + 2 if scenario == 'different' else 33
    if len(rows) < end:
        raise AssertionError(f'{food} {scenario}: missing samples after replacement')
    for i, actual in enumerate(rows[:end]):
        java = expected[i]
        if actual['tick'] != rows[0]['tick'] + i:
            raise AssertionError(f'{food} {scenario}: missing guest player tick {i}')
        remaining = 0 if actual['using'] is None else max(0, actual['duration'] - actual['using'])
        actual_values = (actual['slot0_item'], actual['slot0_count'], remaining, actual['hunger'])
        expected_values = (java['item'], int(java['count']), int(java['use_remaining']), int(java['hunger']))
        if actual_values != expected_values or not same_f32(actual['saturation'], java['saturation']):
            raise AssertionError(f'{food} {scenario} player tick {i}, replacement tick {boundary}: Horizon {actual}; Java {java}')
    return boundary


def run(args):
    with (ROOT / 'fixtures/food-replace-java.csv').open() as f:
        references = list(csv.DictReader(f))
    with food_test.trace_file() as trace, fixture_world(args, 'Food Replace LAN', render=True, pack=args.pack,
            env={'HORIZON_TEST_GUEST_FOOD_TRACE': str(trace)}) as host:
        host.command('/gamerule natural_health_regeneration false')
        port = host.call('lan', 'open', 0, 'commands')['port']
        with TemporaryDirectory(prefix='ff-', dir='/tmp') as scratch, mp.joined_client(
                args, Path(scratch), f'127.0.0.1:{port}', GUEST, render=True,
                scenario='food-replace-lan', pack=args.pack) as guest:
            mp.until('guest join', lambda: any(p['name'] == GUEST and p['placed'] for p in host.call('lan', 'status')['guests']))
            host.command(f'/gamemode survival {GUEST}')
            for index, food in enumerate(FOODS):
                for scenario in ('different', 'same'):
                    food_test.prepare_hunger(host, trace)
                    item = f'create:{food}'
                    replacement = item if scenario == 'same' else f'create:{FOODS[(index + 1) % len(FOODS)]}'
                    host.command(f'/item replace entity {GUEST} hotbar.0 with {item}')
                    mp.until('food reaches guest', lambda: mp.count(guest, item) == 1)
                    guest.call('select', item)
                    offset = len(food_test.trace_rows(trace))
                    guest.call('mouse', 'right', 'down')
                    try:
                        mp.until('food in use', lambda: any(r['using'] is not None and 6 <= r['using'] < 27 for r in guest_rows(trace, offset)))
                        host.command(f'/item replace entity {GUEST} hotbar.0 with {replacement} 2')
                        def observed():
                            rows = guest_rows(trace, offset)
                            starts = [i for i,r in enumerate(rows) if r['using'] == 0 and r['slot0_item'] == item]
                            if not starts:
                                return None
                            rows = rows[starts[0]:]
                            changes = [i for i,r in enumerate(rows) if r['slot0_count'] == 2]
                            if changes and len(rows) >= (changes[0] + 2 if scenario == 'different' else 33):
                                return rows
                        rows = mp.until('replacement and following player ticks', observed)
                        boundary = compare(food, scenario, rows, references)
                        if scenario == 'different':
                            # End any fresh client use after the old one cancels,
                            # then observe beyond the original completion tick.
                            guest.call('mouse', 'right', 'up')
                            rows = mp.until('post-cancellation ticks', lambda: (r if len(r := guest_rows(trace, offset)) >= 36 else None))
                            start = next(i for i, r in enumerate(rows) if r['using'] == 0 and r['slot0_item'] == item)
                            rows = mp.until('full original use window', lambda: (r if len(r := guest_rows(trace, offset)[start:]) >= 34 else None))
                            for tick, sample in enumerate(rows[boundary:34], boundary):
                                if (sample['hunger'] != 10 or not same_f32(sample['saturation'], 0)
                                        or sample['slot0_item'] != replacement or sample['slot0_count'] != 2):
                                    raise AssertionError(f'{food}: unexpected nutrition or inventory at tick {tick}: {sample}')
                    finally:
                        guest.call('mouse', 'right', 'up')
                    print(f'{food} {scenario}: matched Java through replacement at guest tick {boundary}.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    run(parser.parse_args())
