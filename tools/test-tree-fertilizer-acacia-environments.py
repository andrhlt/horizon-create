#!/usr/bin/env python3
"""Compare seeded acacia growth through obstacles and on coarse dirt.

Generate each Java case with java-tree-fertilizer-acacia-geometry-trace.patch,
ACACIA_FIXTURE_ENV and ACACIA_FIXTURE_SEED; remove the disposable clone's
run/world before each offline game-test run to clear scheduled ticks.
"""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')
read_nbt = import_module('test-schematic-capture').read_nbt
ITEM = 'create:tree_fertilizer'


def run(args):
    with (ROOT / 'fixtures/tree_fertilizer_acacia_environments-java.csv').open() as source:
        rows = list(csv.DictReader(source))
    failures = []
    for scenario, seed in args.cases:
        expected = {(int(r['tick']), int(r['x']), int(r['y']), int(r['z'])): r['state']
                    for r in rows if int(r['seed']) == seed and r['scenario'] == scenario}
        if not expected:
            raise ValueError(f'No Java data for seed {seed}')
        with TemporaryDirectory(prefix='acacia-capture-') as scratch:
            output = Path(scratch) / 'tree.nbt'
            with fixture_world(args, 'Acacia Geometry', render=True, pack=args.pack, env={
                'HORIZON_NO_AUDIO': '1', 'CREATE_TREE_FERTILIZER_TRACE_SEED': str(seed),
                'CREATE_TEST_SCHEMATIC_CAPTURE': str(output),
            }) as world:
                world.commands((
                    '/fill -2 169 10 22 169 34 minecraft:dirt',
                    '/fill -2 170 10 22 194 34 minecraft:air',
                    '/tp @s 10.5 170 25.5', '/gamemode survival',
                    f'/item replace entity @s hotbar.0 with {ITEM} 2',
                ))
                if scenario == 'barriers':
                    world.commands(('/setblock 10 172 22 minecraft:bedrock',
                                    '/setblock 11 174 22 minecraft:stone',
                                    '/setblock 8 176 22 minecraft:stone',
                                    '/setblock 12 176 20 minecraft:bedrock'))
                elif scenario == 'canopy':
                    world.commands(('/setblock 10 172 22 minecraft:bedrock',
                                    '/setblock 10 173 22 minecraft:stone',
                                    '/setblock 8 177 19 minecraft:stone',
                                    '/setblock 12 177 20 minecraft:bedrock'))
                elif scenario in ('coarse', 'grass', 'podzol', 'mud', 'mycelium', 'moss', 'muddy_roots'):
                    soil_names = {'coarse': 'coarse_dirt', 'grass': 'grass_block', 'podzol': 'podzol', 'mud': 'mud', 'mycelium': 'mycelium', 'moss': 'moss_block', 'muddy_roots': 'muddy_mangrove_roots'}
                    world.command(f'/setblock 10 169 22 minecraft:{soil_names[scenario]}')
                world.command('/setblock 10 170 22 minecraft:acacia_sapling[stage=0]')
                mp.until('fertilizer delivery', lambda: mp.count(world, ITEM) == 2)
                world.call('select', ITEM)
                world.call('look-at', 10.5, 170.35, 22.5)
                mp.until('sapling target', lambda:
                         (world.call('looking-at').get('block') or {}).get('pos') == [10, 170, 22])
                start = world.clock()
                world.call('mouse', 'right', 'click')
                world.call('wait', 4)
                assert world.clock() == start, 'Frozen game advanced during use'
                soil = world.call('block', 10, 169, 22)['block']
                soil_names = {'coarse': 'coarse_dirt', 'grass': 'grass_block', 'podzol': 'podzol', 'mud': 'mud', 'mycelium': 'mycelium', 'moss': 'moss_block', 'muddy_roots': 'muddy_mangrove_roots'}
                expected_soil = 'minecraft:' + soil_names.get(scenario, 'dirt')
                assert soil == expected_soil, (scenario, seed, soil, expected_soil)
                for tick in range(4):
                    if tick:
                        world.step_to(start + tick)
                    world.call('create-test-schematic-capture', -2, 170, 10, 22, 194, 34)
                    tag = read_nbt(output)
                    actual = {}
                    for block in tag['blocks']:
                        x, y, z = block['pos']
                        state = tag['palette'][block['state']]
                        name = state['id']
                        properties = state.get('properties', {})
                        if name != 'minecraft:air':
                            suffix = '[' + ','.join(f'{k}={v}' for k, v in sorted(properties.items())) + ']' if properties else ''
                            actual[(x - 12, y, z - 12)] = name + suffix
                    actual[(0, -1, 0)] = world.call('block', 10, 169, 22)['state']
                    reference = {(x, y, z): state for (t, x, y, z), state in expected.items() if t == tick}
                    differences = [(pos, reference.get(pos), actual.get(pos))
                                   for pos in sorted(reference.keys() | actual.keys())
                                   if reference.get(pos) != actual.get(pos)]
                    remaining = mp.count(world, ITEM)
                    print(f'{scenario} seed {seed}, tick {tick}: {len(reference)} Java blocks, '
                          f'{len(actual)} Horizon blocks, {len(differences)} differences, '
                          f'{remaining} fertilizer remaining', flush=True)
                    if differences or remaining != 1:
                        failures.append((seed, tick, remaining, differences))
    if failures:
        raise AssertionError(f'Java/Horizon acacia differences: {failures}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--cases', nargs='+', type=lambda x: (x.split(':')[0], int(x.split(':')[1])),
                        default=[('barriers', 13), ('barriers', 16), ('barriers', 19),
                                 ('barriers', 22), ('canopy', 13), ('coarse', 14), ('coarse', 20),
                                 ('grass', 13), ('grass', 20), ('podzol', 13), ('podzol', 20),
                                 ('mud', 13), ('mud', 20), ('mycelium', 13), ('moss', 13), ('muddy_roots', 13)])
    run(parser.parse_args())
