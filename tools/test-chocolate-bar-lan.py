#!/usr/bin/env python3
"""Compare Bar of Chocolate use and stack replacement with pinned Java.

All three cases run even if an earlier case disagrees; the process exits with
failure if any mismatch occurs. The Java reference uses survival FakePlayers.
"""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world
from food_trace import same_f32

food = import_module('test-food-use-lan')
replace = import_module('test-food-replace-lan')
mp = import_module('test-multiplayer')
GUEST = food.GUEST
ITEM = 'create:bar_of_chocolate'


def guest_rows(trace, offset):
    return [r for r in food.trace_rows(trace)[offset:] if r['player'] == GUEST]


def run(args):
    with (ROOT / 'fixtures/chocolate-bar-java.csv').open() as f:
        refs = list(csv.DictReader(f))
    errors = []
    with food.trace_file() as trace, fixture_world(args, 'Chocolate Bar LAN', render=True, pack=args.pack,
            env={'HORIZON_TEST_GUEST_FOOD_TRACE': str(trace)}) as host:
        host.command('/gamerule natural_health_regeneration false')
        port = host.call('lan', 'open', 0, 'commands')['port']
        with TemporaryDirectory(prefix='cb-', dir='/tmp') as scratch, mp.joined_client(
                args, Path(scratch), f'127.0.0.1:{port}', GUEST, render=True,
                scenario='chocolate-bar-lan', pack=args.pack) as guest:
            mp.until('guest join', lambda: any(p['name'] == GUEST and p['placed'] for p in host.call('lan', 'status')['guests']))
            host.command(f'/gamemode survival {GUEST}')
            for scenario in ('normal', 'different', 'same'):
                food.prepare_hunger(host, trace)
                host.command(f'/item replace entity {GUEST} hotbar.0 with {ITEM}')
                mp.until('bar reaches guest', lambda: mp.count(guest, ITEM) == 1)
                guest.call('select', ITEM)
                offset = len(food.trace_rows(trace))
                guest.call('mouse', 'right', 'down')
                try:
                    if scenario != 'normal':
                        mp.until('bar in use', lambda: any(r['using'] is not None and 6 <= r['using'] < 27 for r in guest_rows(trace, offset)))
                        replacement = ITEM if scenario == 'same' else 'create:sweet_roll'
                        host.command(f'/item replace entity {GUEST} hotbar.0 with {replacement} 2')
                    def window():
                        r = guest_rows(trace, offset)
                        starts = [i for i,x in enumerate(r) if x['using'] == 0 and x['slot0_item'] == ITEM]
                        if not starts:
                            return None
                        r = r[starts[0]:]
                        if scenario == 'normal':
                            return r[:36] if len(r) >= 36 else None
                        changes = [i for i,x in enumerate(r) if x['slot0_count'] == 2]
                        length = (changes[0] + 2 if scenario == 'different' else 33) if changes else None
                        return r if length is not None and len(r) >= length else None
                    samples = mp.until(f'{scenario} bar observation', window)
                    try:
                        if scenario == 'normal':
                            expected = [r for r in refs if r['scenario'] == 'normal' and r['boundary'] == '0'][:36]
                            food.compare('bar_of_chocolate', expected, samples)
                        else:
                            comparison_refs = refs
                            if scenario == 'different':
                                boundary = next(i for i, sample in enumerate(samples) if sample['slot0_count'] == 2)
                                next_tick = samples[boundary + 1]
                                if next_tick['using'] == 0 and next_tick['used_item'] == replacement:
                                    # An additional actual packet started the replacement
                                    # food after cancellation, within this guest tick.
                                    comparison_refs = [dict(row, scenario='different')
                                                       for row in refs if row['scenario'] == 'different_repeat']
                            boundary = replace.compare('bar_of_chocolate', scenario, samples, comparison_refs)
                            if scenario == 'different':
                                # Release any separately initiated use and observe
                                # the original bar's whole completion window.
                                guest.call('mouse', 'right', 'up')
                                def extended():
                                    r = guest_rows(trace, offset)
                                    starts = [i for i,x in enumerate(r) if x['using'] == 0 and x['slot0_item'] == ITEM]
                                    if starts and len(r) >= starts[0] + 34:
                                        return r[starts[0]:starts[0] + 34]
                                later = mp.until('post-cancellation original use window', extended)
                                for tick, sample in enumerate(later[boundary:], boundary):
                                    if (sample['tick'] != later[0]['tick'] + tick
                                            or sample['slot0_item'] != replacement or sample['slot0_count'] != 2
                                            or sample['hunger'] != 10 or not same_f32(sample['saturation'], 0)):
                                        raise AssertionError(f'different: delayed item loss or nutrition at tick {tick}: {sample}')
                    except AssertionError as error:
                        errors.append((scenario, str(error)))
                        print(f'{scenario}: MISMATCH {error}', flush=True)
                    else:
                        print(f'{scenario}: Java comparison passed.', flush=True)
                finally:
                    guest.call('mouse', 'right', 'up')
    if errors:
        raise AssertionError(f'{len(errors)} chocolate bar scenario(s) disagreed with Java: {[x[0] for x in errors]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    run(parser.parse_args())
