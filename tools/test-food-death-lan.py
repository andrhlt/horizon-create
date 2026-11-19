#!/usr/bin/env python3
"""Compare LAN death/respawn while eating with Java's respawn state transfer.

Java invokes ServerPlayer.die and the restoreFrom(false) state transfer used
by PlayerList.respawn; its fixture connection does not exercise Java respawn
packet delivery. LAN uses a normal guest death and respawn with keepInventory.
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


def prepare_hunger(host, trace):
    host.command(f'/effect give {GUEST} minecraft:hunger 240 15 true')
    def ready():
        rows = guest_rows(trace)
        if not rows:
            return False
        if rows[-1]['hunger'] < 10:
            raise AssertionError(f'Hunger setup overshot: {rows[-1]}')
        return rows[-1]['hunger'] == 10 and same_f32(rows[-1]['saturation'], 0)
    mp.until('guest hunger setup', ready, seconds=180)
    host.command(f'/effect clear {GUEST} minecraft:hunger')


def run(args):
    with (ROOT / 'fixtures/food-death-java.csv').open() as f:
        states = list(csv.DictReader(f))
    with (ROOT / 'fixtures/food-death-ticks-java.csv').open() as f:
        ticks = list(csv.DictReader(f))
    with food_test.trace_file() as trace, fixture_world(args, 'Food Death LAN', render=True, pack=args.pack,
            env={'HORIZON_TEST_GUEST_FOOD_TRACE': str(trace)}) as host:
        host.command('/gamerule natural_health_regeneration false')
        host.command('/gamerule keep_inventory true')
        rule = host.command('/gamerule keep_inventory')
        if 'true' not in rule.lower():
            raise AssertionError(f'keep_inventory was not enabled: {rule}')
        port = host.call('lan', 'open', 0, 'commands')['port']
        with TemporaryDirectory(prefix='fd-', dir='/tmp') as scratch, mp.joined_client(
                args, Path(scratch), f'127.0.0.1:{port}', GUEST, render=True,
                scenario='food-death-lan', pack=args.pack) as guest:
            mp.until('guest join', lambda: any(p['name'] == GUEST and p['placed'] for p in host.call('lan', 'status')['guests']))
            host.command(f'/gamemode survival {GUEST}')
            for food in food_test.FOODS:
                host.call('command', f'/clear {GUEST}')
                prepare_hunger(host, trace)
                item = f'create:{food}'
                host.command(f'/item replace entity {GUEST} hotbar.0 with {item}')
                mp.until('food reaches guest', lambda: mp.count(guest, item) == 1)
                guest.call('select', item)
                offset = len(food_test.trace_rows(trace))
                guest.call('mouse', 'right', 'down')
                mp.until('food in use', lambda: any(r['using'] is not None and 6 <= r['using'] < 30 for r in guest_rows(trace, offset)))
                host.command(f'/kill {GUEST}')
                mp.until('death screen', lambda: guest.call('status')['screen'] == 'dead')
                before = guest_rows(trace, offset)
                if not before or before[-1]['using'] is None or before[-1]['slot0_item'] != item:
                    raise AssertionError(f'{food}: last player tick was not active eating: {before[-1:]}')
                ref_before = next(x for x in states if x['food'] == food and x['stage'] == 'before')
                if (before[-1]['slot0_count'] != int(ref_before['count']) or before[-1]['hunger'] != int(ref_before['hunger'])
                        or not same_f32(before[-1]['saturation'], ref_before['saturation'])):
                    raise AssertionError(f'{food}: pre-death state {before[-1]} != {ref_before}')
                after_offset = len(food_test.trace_rows(trace))
                guest.call('respawn')
                mp.until('playing after respawn', lambda: guest.call('status')['screen'] == 'playing')
                guest.call('mouse', 'right', 'up')
                rows = mp.until('respawn player ticks', lambda: (r if len(r := guest_rows(trace, after_offset)) >= 4 else None))
                ref = next(x for x in states if x['food'] == food and x['stage'] == 'respawn')
                for sample in rows:
                    if (sample['using'] is not None or sample['slot0_item'] != item
                            or sample['slot0_count'] != int(ref['count']) or sample['hunger'] != int(ref['hunger'])
                            or not same_f32(sample['saturation'], ref['saturation'])):
                        raise AssertionError(f'{food}: respawn state {sample} != Java {ref}')
                mp.until('retained food reaches guest', lambda: mp.count(guest, item) == 1)
                prepare_hunger(host, trace)
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
                    food_test.compare(food, [r for r in ticks if r['food'] == food], samples)
                    mp.until('consumption reaches guest', lambda: mp.count(guest, item) == 0)
                finally:
                    guest.call('mouse', 'right', 'up')
                print(f"{food}: died after observed use tick {before[-1]['using']}, respawned with food and reset use, restarted and matched 36 Java ticks.", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    run(parser.parse_args())
