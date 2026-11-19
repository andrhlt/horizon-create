#!/usr/bin/env python3
"""Verify Tree Fertilizer in both hands uses only the mainhand stack.

Apply java-tree-fertilizer-acacia-geometry-trace.patch to the pinned Java
clone; set TREE_FIXTURE_BOTH=true, TREE_FIXTURE_SPECIES=oak and seed 9. Remove
the disposable clone's run/world before each offline game test. Its full tree
and soil states match the shared species geometry fixture.
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
    with (ROOT / 'fixtures/tree_fertilizer_species_geometry-java.csv').open() as source:
        rows = list(csv.DictReader(source))
    failures = []
    for species, seed in args.cases:
        expected = {(int(r['tick']), int(r['x']), int(r['y']), int(r['z'])): r['state']
                    for r in rows if int(r['seed']) == seed and r['species'] == species}
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
                    f'/setblock 10 170 22 minecraft:{species}_sapling[stage=0]',
                    f'/item replace entity @s hotbar.0 with {ITEM} 2',
                    f'/item replace entity @s weapon.offhand with {ITEM} 3',
                ))
                mp.until('fertilizer delivery', lambda: (world.call('inventory')['offhand'] or {}).get('count') == 3)
                world.call('select', ITEM)
                world.call('look-at', 10.5, 170.35, 22.5)
                mp.until('sapling target', lambda:
                         (world.call('looking-at').get('block') or {}).get('pos') == [10, 170, 22])
                start = world.clock()
                world.call('mouse', 'right', 'click')
                world.call('wait', 4)
                assert world.clock() == start, 'Frozen game advanced during use'
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
                    inventory = world.call('inventory')
                    main = inventory['held'] or {}
                    offhand = inventory['offhand'] or {}
                    remaining = main.get('count', 0) if main.get('item') == ITEM else 0
                    off_count = offhand.get('count', 0) if offhand.get('item') == ITEM else 0
                    print(f'{species} seed {seed}, tick {tick}: {len(reference)} Java blocks, '
                          f'{len(actual)} Horizon blocks, {len(differences)} differences, '
                          f'{remaining} mainhand and {off_count} offhand remaining', flush=True)
                    if differences or remaining != 1 or off_count != 3:
                        failures.append((seed, tick, remaining, off_count, differences))
    if failures:
        raise AssertionError(f'Java/Horizon tree differences: {failures}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--cases', nargs='+', type=lambda x: (x.split(':')[0], int(x.split(':')[1])),
                        default=[('oak', 9)])
    run(parser.parse_args())
