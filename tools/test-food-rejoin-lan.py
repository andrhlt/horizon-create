#!/usr/bin/env python3
"""Compare Java's player save/load during eating with LAN disconnect and rejoin.

The Java oracle calls PlayerList.remove and PlayerList.load with a connected
FakePlayer, then ticks the restored player. LAN uses a real guest connection;
its last recorded pre-disconnect player tick and restored state are sampled.
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


def guest_rows(trace, offset=0):
    return [r for r in food_test.trace_rows(trace)[offset:] if r['player'] == GUEST]


def joined(host):
    return any(p['name'] == GUEST and p['placed'] for p in host.call('lan', 'status')['guests'])


def run(args):
    with (ROOT / 'fixtures/food-rejoin-java.csv').open() as f:
        states = list(csv.DictReader(f))
    with (ROOT / 'fixtures/food-rejoin-ticks-java.csv').open() as f:
        ticks = list(csv.DictReader(f))
    with food_test.trace_file() as trace, fixture_world(args, 'Food Rejoin LAN', render=True, pack=args.pack,
            env={'HORIZON_TEST_GUEST_FOOD_TRACE': str(trace)}) as host:
        host.command('/gamerule naturalRegeneration false')
        port = host.call('lan', 'open', 0, 'commands')['port']
        with TemporaryDirectory(prefix='fr-', dir='/tmp') as scratch:
            root = Path(scratch)
            for number, food in enumerate(food_test.FOODS):
                item = f'create:{food}'
                before_home = root / f'b{number}'
                before_home.mkdir()
                with mp.joined_client(args, before_home, f'127.0.0.1:{port}', GUEST, render=True,
                                      scenario='food-rejoin-before', pack=args.pack) as guest:
                    mp.until('guest join', lambda: joined(host))
                    if number == 0:
                        host.command(f'/gamemode survival {GUEST}')
                    mp.until('survival mode', lambda: any(p['name'] == GUEST and p['game_mode'] == 0 for p in host.call('lan', 'status')['guests']))
                    food_test.prepare_hunger(host, trace)
                    host.command(f'/item replace entity {GUEST} hotbar.0 with {item}')
                    mp.until('food inventory sync', lambda: mp.count(guest, item) == 1)
                    guest.call('select', item)
                    offset = len(food_test.trace_rows(trace))
                    guest.call('mouse', 'right', 'down')
                    mp.until('food use before disconnect', lambda: any(r['using'] is not None and 6 <= r['using'] < 30 for r in guest_rows(trace, offset)))
                    guest.call('quit')
                    mp.until('guest client exit', lambda: not guest.socket.exists())
                mp.until('guest disconnect', lambda: not joined(host))
                before = guest_rows(trace, offset)
                if not before or before[-1]['using'] is None or before[-1]['slot0_item'] != item:
                    raise AssertionError(f'{food}: last player tick was not active eating: {before[-1:]}')
                ref_before = next(x for x in states if x['food'] == food and x['stage'] == 'disconnect')
                if (before[-1]['slot0_count'] != int(ref_before['count']) or before[-1]['hunger'] != int(ref_before['hunger'])
                        or not same_f32(before[-1]['saturation'], ref_before['saturation'])):
                    raise AssertionError(f'{food}: state before disconnect: {before[-1]} != {ref_before}')
                after_home = root / f'a{number}'
                after_home.mkdir()
                offset = len(food_test.trace_rows(trace))
                with mp.joined_client(args, after_home, f'127.0.0.1:{port}', GUEST, render=True,
                                      scenario='food-rejoin-after', pack=args.pack) as guest:
                    mp.until('guest rejoin', lambda: joined(host))
                    mp.until('survival mode restored', lambda: any(p['name'] == GUEST and p['game_mode'] == 0 for p in host.call('lan', 'status')['guests']))
                    mp.until('saved food reaches guest', lambda: mp.count(guest, item) == 1)
                    samples = mp.until('rejoined guest player ticks', lambda: (r if len(r := guest_rows(trace, offset)) >= 4 else None))
                    ref_after = next(x for x in states if x['food'] == food and x['stage'] == 'rejoin')
                    for sample in samples:
                        if (sample['using'] is not None or sample['slot0_item'] != item
                                or sample['slot0_count'] != int(ref_after['count'])
                                or sample['hunger'] != int(ref_after['hunger'])
                                or not same_f32(sample['saturation'], ref_after['saturation'])):
                            raise AssertionError(f'{food}: rejoined state: {sample} != {ref_after}')
                    guest.call('select', item)
                    start_offset = len(food_test.trace_rows(trace))
                    guest.call('mouse', 'right', 'down')
                    try:
                        def restarted():
                            records = guest_rows(trace, start_offset)
                            starts = [i for i,r in enumerate(records) if r['using'] == 0 and r['slot0_item'] == item]
                            if starts and len(records) >= starts[0] + 36:
                                return records[starts[0]:starts[0] + 36]
                        samples = mp.until('36 restarted guest player ticks', restarted)
                        expected = [r for r in ticks if r['food'] == food]
                        food_test.compare(food, expected, samples)
                        mp.until('consumption reaches guest', lambda: mp.count(guest, item) == 0)
                    finally:
                        guest.call('mouse', 'right', 'up')
                mp.until('guest leaves after consumption', lambda: not joined(host))
                print(f"{food}: disconnected after observed use tick {before[-1]['using']}, rejoined idle with food, restarted and matched 36 Java ticks.", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    run(parser.parse_args())
