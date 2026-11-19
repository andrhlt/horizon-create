#!/usr/bin/env python3
"""Compare interrupted and restarted LAN guest eating with pinned Java player ticks.

The reusable test anchors interruption to its observed guest player tick. It
validates Java's four identical canceled idle samples before extending that
state to the observed pause. The archived six-schedule replay compares 308
consecutive rows directly with the exact-schedule Java capture via
tools/compare-food-interrupt-exact.py.
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


def rows_for(trace, offset):
    return [r for r in food_test.trace_rows(trace)[offset:] if r['player'] == GUEST]


def compare(food, scenario, rows, refs):
    start = next(i for i, row in enumerate(rows) if row['using'] == 0 and row['slot0_item'] == f'create:{food}')
    rows = rows[start:]
    interrupted = next(i for i, row in enumerate(rows[1:], 1) if row['using'] is None)
    restarted = next(i for i, row in enumerate(rows[interrupted + 1:], interrupted + 1) if row['using'] == 0)
    if not 1 <= interrupted <= 31:
        raise AssertionError(f'{food} {scenario}: interruption after {interrupted} ticks')
    expected = [r for r in refs if r['food'] == food and r['scenario'] == scenario and int(r['boundary']) == interrupted]
    if len(expected) != interrupted + 40:
        raise AssertionError('Java reference incomplete')
    # Java holds each canceled state for four samples. Check that they are
    # equivalent before extending that state to the observed LAN pause length.
    idle_fields = ('selected', 'item', 'count', 'use_remaining', 'hunger', 'saturation')
    idle = tuple(expected[interrupted][key] for key in idle_fields)
    if any(tuple(row[key] for key in idle_fields) != idle
           for row in expected[interrupted:interrupted + 4]):
        raise AssertionError(f'{food} {scenario}: Java canceled state changed during pause')
    for tick, actual in enumerate(rows[:restarted + 36]):
        if actual['tick'] != rows[0]['tick'] + tick:
            raise AssertionError(f'{food} {scenario}: missing guest tick {tick}')
        # Java restarted four ticks after interruption. Align that real action
        # to its observed LAN start; intermediate canceled ticks are identical.
        reference_tick = tick if tick < interrupted else (interrupted if tick < restarted else interrupted + 4 + tick - restarted)
        exp = expected[reference_tick]
        # The guest may select slot zero before pressing use again. Java's
        # release scenario records the same idle state with that slot selected.
        if scenario == 'swap' and interrupted <= tick < restarted and actual['selected'] == 0:
            exp = next(r for r in refs if r['food'] == food and r['scenario'] == 'release'
                       and int(r['boundary']) == interrupted and int(r['tick']) == interrupted)
        remaining = max(0, actual['duration'] - actual['using']) if actual['using'] is not None else 0
        values = (actual['selected'], actual['slot0_item'], actual['slot0_count'], remaining, actual['hunger'])
        want = (int(exp['selected']), exp['item'], int(exp['count']), int(exp['use_remaining']), int(exp['hunger']))
        selected_stack = (actual['item'], actual['count'])
        expected_hand = (exp['item'], int(exp['count'])) if int(exp['selected']) == 0 else ('minecraft:air', 0)
        if (values != want or selected_stack != expected_hand
                or not same_f32(actual['saturation'], exp['saturation'])):
            raise AssertionError(f'{food} {scenario} guest tick {tick}, Java tick {reference_tick}: {actual} != {exp}')
    if len(rows) < restarted + 36:
        raise AssertionError(f'{food} {scenario}: incomplete restart trace')
    return interrupted, restarted


def run(args):
    with (ROOT / 'fixtures/food-interrupt-java.csv').open() as source:
        refs = list(csv.DictReader(source))
    with food_test.trace_file() as trace, fixture_world(args, 'Food Interrupt LAN', render=True, pack=args.pack,
            env={'HORIZON_TEST_GUEST_FOOD_TRACE': str(trace)}) as host:
        host.command('/gamerule naturalRegeneration false')
        port = host.call('lan', 'open', 0, 'commands', 'force')['port']
        with TemporaryDirectory(prefix='hc-food-interrupt-lan-') as scratch, mp.joined_client(
                args, Path(scratch), f'127.0.0.1:{port}', GUEST, render=True,
                scenario='food-interrupt-lan', pack=args.pack) as guest:
            mp.until('guest join', lambda: any(p['name'] == GUEST and p['placed'] for p in host.call('lan', 'status')['guests']))
            host.command(f'/gamemode survival {GUEST}')
            for food in FOODS:
                for scenario in ('release', 'swap'):
                    food_test.prepare_hunger(host, trace)
                    item = f'create:{food}'
                    host.command(f'/item replace entity {GUEST} hotbar.0 with {item}')
                    mp.until('food inventory sync', lambda: mp.count(guest, item) == 1)
                    guest.call('select', item)
                    mp.until('selected food on host', lambda: any(r['selected'] == 0 and r['slot0_item'] == item for r in rows_for(trace, 0)[-2:]))
                    offset = len(food_test.trace_rows(trace))
                    guest.call('mouse', 'right', 'down')
                    try:
                        mp.until('active guest use', lambda: any(r['using'] is not None and r['using'] >= 6 for r in rows_for(trace, offset)))
                        if scenario == 'release':
                            guest.call('mouse', 'right', 'up')
                        else:
                            guest.call('key', '2', 'tap')
                            mp.until('guest hotbar interruption', lambda: any(r['using'] is None and r['selected'] == 1 for r in rows_for(trace, offset)))
                            guest.call('mouse', 'right', 'up')
                        def interrupted():
                            records = rows_for(trace, offset)
                            starts = [i for i,r in enumerate(records) if r['using'] == 0]
                            return starts and any(r['using'] is None for r in records[starts[0]+1:])
                        mp.until('interruption receipt', interrupted)
                        guest.call('select', item)
                        mp.until('food slot selected again', lambda: rows_for(trace, offset)[-1]['selected'] == 0)
                        guest.call('mouse', 'right', 'down')
                        def complete():
                            records = rows_for(trace, offset)
                            starts = [i for i,r in enumerate(records) if r['using'] == 0 and r['slot0_item'] == item]
                            if len(starts) >= 2 and len(records) >= starts[1] + 36:
                                return records
                        records = mp.until('restarted guest use trace', complete)
                        boundary, restarted = compare(food, scenario, records, refs)
                        mp.until('guest consumption sync', lambda: mp.count(guest, item) == 0)
                    finally:
                        guest.call('mouse', 'right', 'up')
                    print(f'{food} {scenario}: Java matched, interrupted at player tick {boundary}, restarted at {restarted}.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    run(parser.parse_args())
