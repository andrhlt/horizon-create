#!/usr/bin/env python3
"""Compare Tree Fertilizer overlay item drops with pinned Java.

Apply java-tree-fertilizer-drops-trace.patch to the pinned Java clone; set
TREE_FIXTURE_SPECIES=oak, ACACIA_FIXTURE_SEED=9 and ACACIA_FIXTURE_ENV to the
case. Delete the disposable clone's run/world before each offline game test.
"""
import argparse
import collections
import csv
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT, fixture_world
mp = import_module('test-multiplayer')
ITEM = 'create:tree_fertilizer'


def run(args):
    with (ROOT / 'fixtures/tree_fertilizer_drops-java.csv').open() as source:
        rows = list(csv.DictReader(source))
    failures = []
    for scenario in args.cases:
        with fixture_world(args, 'Fertilizer Drops', render=True, pack=args.pack, env={
            'HORIZON_NO_AUDIO': '1', 'CREATE_TREE_FERTILIZER_TRACE_SEED': '9',
        }) as world:
            obstruction = 'stone' if scenario == 'drop_stone' else 'oak_planks'
            world.commands((
                '/fill 5 169 17 15 169 27 minecraft:dirt',
                '/fill 5 170 17 15 186 27 minecraft:air',
                '/tp @s 10.5 170 25.5', '/gamemode survival',
                f'/setblock 10 172 22 minecraft:{obstruction}',
                '/setblock 10 170 22 minecraft:oak_sapling[stage=0]',
                f'/item replace entity @s hotbar.0 with {ITEM} 2',
            ))
            mp.until('fertilizer delivery', lambda: mp.count(world, ITEM) == 2)
            world.call('select', ITEM)
            world.call('look-at', 10.5, 170.35, 22.5)
            mp.until('sapling target', lambda:
                     (world.call('looking-at').get('block') or {}).get('pos') == [10, 170, 22])
            start = world.clock()
            world.call('mouse', 'right', 'click')
            world.call('wait', 4)
            assert world.clock() == start
            assert world.call('block', 10, 170, 22)['block'] == 'minecraft:oak_log'
            assert world.call('block', 10, 172, 22)['block'] == 'minecraft:oak_log'
            for tick in range(4):
                if tick:
                    world.step_to(start + tick)
                entities = world.call('entities', 12, 'minecraft:item')['entities']
                actual = collections.Counter()
                for entity in entities:
                    actual[entity['item']['item']] += entity['item']['count']
                reference = collections.Counter({r['item']: int(r['count']) for r in rows
                                                 if r['scenario'] == scenario and int(r['tick']) == tick})
                expected_entities = {int(r['entity_count']) for r in rows
                                     if r['scenario'] == scenario and int(r['tick']) == tick}
                assert len(expected_entities) == 1, (scenario, tick, expected_entities)
                expected_entities = expected_entities.pop()
                remaining = mp.count(world, ITEM)
                print(f'{scenario} tick {tick}: Java {dict(reference)}, Horizon {dict(actual)}, '
                      f'entities {len(entities)}, remaining {remaining}', flush=True)
                if actual != reference or len(entities) != expected_entities or remaining != 1:
                    failures.append((scenario, tick, dict(reference), dict(actual), remaining))
    if failures:
        raise AssertionError(failures)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--cases', nargs='+', default=['drop_stone', 'drop_planks'])
    run(parser.parse_args())
