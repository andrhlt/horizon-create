#!/usr/bin/env python3
"""Compare full-hunger refusal and creative eating against pinned Java.

The full-hunger case samples 36 consecutive server guest ticks after normal
mouse input and a subsequent command response on that guest connection. The
creative case anchors each trace to the actual use-start player tick.
"""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world
from food_trace import same_f32

food_test = import_module('test-food-use-lan')
mp = import_module('test-multiplayer')
GUEST = food_test.GUEST
FOODS = food_test.FOODS


def rows(trace, offset):
    return [r for r in food_test.trace_rows(trace)[offset:] if r['player'] == GUEST]


def compare(food, scenario, samples, refs):
    if len(samples) != 36:
        raise AssertionError(f'{food} {scenario}: incomplete trace')
    # Java captures a separate actual input at each possible restart tick.
    restart = next((i for i, r in enumerate(samples[32:], 32)
                    if r['using'] == 0), None) if scenario == 'creative' else None
    java_mode = f'creative_repeat{restart}' if restart is not None else scenario
    expected = [x for x in refs if x['food'] == food and x['scenario'] == java_mode]
    if len(expected) != 36:
        raise AssertionError(f'{food} {java_mode}: incomplete Java trace')
    for tick, (actual, java) in enumerate(zip(samples, expected, strict=True)):
        if actual['tick'] != samples[0]['tick'] + tick:
            raise AssertionError(f'{food} {scenario}: missing player tick {tick}')
        remaining = 0 if actual['using'] is None else actual['duration'] - actual['using']
        values = (actual['slot0_item'], actual['slot0_count'], remaining, actual['hunger'])
        want = (java['item'], int(java['count']), int(java['use_remaining']), int(java['hunger']))
        if values != want or not same_f32(actual['saturation'], java['saturation']):
            raise AssertionError(f'{food} {scenario} player tick {tick}: {actual} != Java {java}')
    return java_mode


def run(args):
    with (ROOT / 'fixtures/food-mode-java.csv').open() as f:
        refs = list(csv.DictReader(f))
    with (ROOT / 'fixtures/food-mode-actions-java.csv').open() as f:
        actions = list(csv.DictReader(f))
    with food_test.trace_file() as trace, fixture_world(args, 'Food Mode LAN', render=True, pack=args.pack,
            env={'HORIZON_TEST_GUEST_FOOD_TRACE': str(trace)}) as host:
        host.command('/gamerule natural_health_regeneration false')
        port = host.call('lan', 'open', 0, 'commands')['port']
        with TemporaryDirectory(prefix='fm-', dir='/tmp') as scratch, mp.joined_client(
                args, Path(scratch), f'127.0.0.1:{port}', GUEST, render=True,
                scenario='food-mode-lan', pack=args.pack) as guest:
            mp.until('guest join', lambda: any(p['name'] == GUEST and p['placed'] for p in host.call('lan', 'status')['guests']))
            host.command(f'/gamemode survival {GUEST}')
            # Separate harmless command responses provide distinct FIFO markers.
            queries = (('foodLevel', 'entity data: 20'), ('foodSaturationLevel', 'entity data: 5'), ('Health', 'entity data: 20'))
            for food, (field, marker) in zip(FOODS, queries, strict=True):
                action = next(x for x in actions if x['food'] == food and x['scenario'] == 'full')
                assert action['result'] == 'FAIL' and action['using'] == 'false'
                host.command(f'/item replace entity {GUEST} hotbar.0 with create:{food}')
                mp.until('food inventory sync', lambda: mp.count(guest, f'create:{food}') == 1)
                guest.call('select', f'create:{food}')
                offset = len(food_test.trace_rows(trace))
                client_tick = guest.call('status')['ticks']
                guest.call('mouse', 'right', 'down')
                try:
                    mp.until('client input ticks', lambda: guest.call('status')['ticks'] >= client_tick + 2)
                    guest.call('chat', f'/data get entity @s {field}')
                    mp.until('server response after guest input', lambda: any(marker in str(line) for line in guest.call('chat-log', 100)['chat']))
                    # Validate the interval from the input through the server's
                    # FIFO response, then sample 36 further player ticks.
                    before_ack = rows(trace, offset)
                    for sample in before_ack:
                        if (sample['using'] is not None or sample['slot0_item'] != f'create:{food}'
                                or sample['slot0_count'] != 1 or sample['hunger'] != 20
                                or not same_f32(sample['saturation'], 5)):
                            raise AssertionError(f'{food}: state before command response: {sample}')
                    after_ack = len(food_test.trace_rows(trace))
                    samples = mp.until('full-hunger observation window after response',
                                       lambda: (r[:36] if len(r := rows(trace, after_ack)) >= 36 else None))
                    compare(food, 'full', samples, refs)
                    if (guest.call('status')['held'] or {}).get('item') != f'create:{food}':
                        raise AssertionError(f'{food}: guest did not retain food')
                finally:
                    guest.call('mouse', 'right', 'up')
                print(f'{food} full hunger: no use or nutrition over 36 guest ticks; food retained.', flush=True)
            for food in FOODS:
                food_test.prepare_hunger(host, trace)
                host.command(f'/gamemode creative {GUEST}')
                host.command(f'/item replace entity {GUEST} hotbar.0 with create:{food}')
                mp.until('food inventory sync', lambda: mp.count(guest, f'create:{food}') == 1)
                guest.call('select', f'create:{food}')
                offset = len(food_test.trace_rows(trace))
                guest.call('mouse', 'right', 'down')
                try:
                    def samples():
                        records = rows(trace, offset)
                        starts = [i for i,r in enumerate(records) if r['using'] == 0 and r['slot0_item'] == f'create:{food}']
                        if starts and len(records) >= starts[0] + 36:
                            return records[starts[0]:starts[0]+36]
                    observed = mp.until('creative guest ticks', samples)
                    mode = compare(food, 'creative', observed, refs)
                finally:
                    guest.call('mouse', 'right', 'up')
                host.command(f'/gamemode survival {GUEST}')
                print(f'{food} creative: 36 guest ticks matched Java {mode}; stack retained.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    run(parser.parse_args())
