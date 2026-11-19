#!/usr/bin/env python3
"""Try real LAN food replacement between use input and its first player tick.

A second LAN guest sends the replacement command. Each attempt reports the
observed packet ordering. A case passes only after the trace proves the old
food started, the new food was held at use tick zero, and 34 contiguous guest
ticks match the corresponding Java trace. Packet scheduling is not controlled,
so a single observed hit does not establish CI repeatability; exhausting the
attempt limit is an explicit failure rather than a skipped test.
"""
import argparse
import csv
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from fixture_world import ROOT, fixture_world
from food_trace import same_f32

food_test = import_module('test-food-use-lan')
mp = import_module('test-multiplayer')
GUEST = food_test.GUEST
FOODS = food_test.FOODS


def rows(trace, offset):
    return [x for x in food_test.trace_rows(trace)[offset:] if x['player'] == GUEST]


def compare(food, observed, java):
    if len(observed) != 34 or len(java) != 38:
        raise AssertionError(f'{food}: incomplete comparison')
    for tick, (actual, expected) in enumerate(zip(observed, java)):
        if actual['tick'] != observed[0]['tick'] + tick:
            raise AssertionError(f'{food}: missing player tick {tick}: {actual}')
        remaining = 0 if actual['using'] is None else actual['duration'] - actual['using']
        actual_state = (actual['slot0_item'], actual['slot0_count'], remaining, actual['hunger'])
        expected_state = (expected['item'], int(expected['count']), int(expected['use_remaining']), int(expected['hunger']))
        if actual_state != expected_state or not same_f32(actual['saturation'], expected['saturation']):
            raise AssertionError(f'{food}: Java tick {tick}: {actual} != {expected}')


def run_case(food, replacement, java, host, guest, operator, trace):
    old, new = f'create:{food}', f'create:{replacement}'
    for attempt in range(60):
        host.command(f'/item replace entity {GUEST} hotbar.0 with {old}')
        mp.until('original food reaches guest', lambda: mp.count(guest, old) == 1)
        guest.call('select', old)
        offset = len(food_test.trace_rows(trace))
        guest.call('mouse', 'right', 'down')
        # Vary scheduling; no wall-clock duration is interpreted as a player tick.
        delay = (attempt % 5) * 0.006
        if delay:
            time.sleep(delay)
        operator.call('chat', f'/item replace entity {GUEST} hotbar.0 with {new} 2')
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            samples = rows(trace, offset)
            if any(r['using'] == 0 for r in samples):
                break
            time.sleep(0.01)
        guest.call('mouse', 'right', 'up')
        samples = rows(trace, offset)
        starts = [r for r in samples if r['using'] == 0]
        print(json.dumps({'food': food, 'attempt': attempt, 'delay_s': delay, 'starts': starts}), flush=True)
        matches = [i for i,r in enumerate(samples) if r['using'] == 0 and r['used_item'] == old
                   and r['slot0_item'] == new and r['slot0_count'] == 2]
        if matches:
            target_tick = samples[matches[0]]['tick']
            def window():
                found = [r for r in rows(trace, offset) if r['tick'] >= target_tick]
                return found[:34] if len(found) >= 34 else None
            observed = mp.until('tick zero replacement window', window)
            if any(r['used_item'] == new for r in observed[1:]):
                print(json.dumps({'food': food, 'attempt': attempt, 'outcome': 'fresh replacement use; exact no-input Java schedule not comparable'}), flush=True)
            else:
                compare(food, observed, java)
                print(f'{food}: 34 contiguous ticks matched Java boundary-zero trace on attempt {attempt}.', flush=True)
                return
        # Settle each missed ordering using ordinary guest controls. Preserve all
        # attempts in the output and raw trace, including any new food use.
        guest.call('key', '2', 'tap')
        settled = mp.until('input release and hotbar change', lambda:
                           (r[-1] if (r := rows(trace, offset)) and r[-1]['using'] is None
                            and r[-1]['selected'] == 1 else None))
        print(json.dumps({'food': food, 'attempt': attempt, 'settled': settled}), flush=True)
        if settled['hunger'] != 10 or not same_f32(settled['saturation'], 0):
            food_test.prepare_hunger(host, trace)
        guest.call('key', '1', 'tap')
    raise AssertionError(f'{food}: no directly comparable tick-zero replacement in 60 ordinary-input attempts')


def run(args):
    with (ROOT / 'fixtures/food-replace-java.csv').open() as f:
        references = list(csv.DictReader(f))
    with food_test.trace_file() as trace, fixture_world(args, 'Food Replace Zero LAN', render=True, pack=args.pack,
            env={'HORIZON_TEST_GUEST_FOOD_TRACE': str(trace)}) as host:
        host.command('/gamerule natural_health_regeneration false')
        port = host.call('lan', 'open', 0, 'commands')['port']
        with TemporaryDirectory(prefix='fz-', dir='/tmp') as scratch, mp.joined_client(
                args, Path(scratch), f'127.0.0.1:{port}', GUEST, render=True,
                scenario='food-replace-zero-lan', pack=args.pack) as guest, mp.joined_client(
                args, Path(scratch), f'127.0.0.1:{port}', 'FoodOperator', render=True,
                scenario='food-replace-zero-operator', pack=args.pack) as operator:
            mp.until('guest join', lambda: any(p['name'] == GUEST and p['placed'] for p in host.call('lan', 'status')['guests']))
            mp.until('operator join', lambda: any(p['name'] == 'FoodOperator' and p['placed'] for p in host.call('lan', 'status')['guests']))
            host.command(f'/gamemode survival {GUEST}')
            food_test.prepare_hunger(host, trace)
            for i, food in enumerate(FOODS):
                reference = [r for r in references if r['food'] == food and r['scenario'] == 'different' and r['boundary'] == '0']
                run_case(food, FOODS[(i + 1) % len(FOODS)], reference, host, guest, operator, trace)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    run(parser.parse_args())
