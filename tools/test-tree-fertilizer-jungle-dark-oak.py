#!/usr/bin/env python3
"""Compare Jungle and Dark Oak trees, including the full soil plane.

Apply java-tree-fertilizer-jungle-dark-oak-trace.patch to the pinned Java
clone. Set TREE_FIXTURE_SPECIES, ACACIA_FIXTURE_ENV (giant, single, giant_obstacles, corner_* or partial_*) and
ACACIA_FIXTURE_SEED for each case. Delete the disposable clone's run/world
before each offline game test to clear previously scheduled ticks.
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
    with (ROOT / 'fixtures/tree_fertilizer_jungle_dark_oak_geometry-java.csv').open() as source:
        rows = list(csv.DictReader(source))
    failures = []
    for species, scenario, seed in args.cases:
        expected = {(int(r['tick']), int(r['x']), int(r['y']), int(r['z'])): r['state']
                    for r in rows if int(r['seed']) == seed and r['species'] == species and r['scenario'] == scenario}
        if not expected:
            raise ValueError(f'No Java data for seed {seed}')
        with TemporaryDirectory(prefix='acacia-capture-') as scratch:
            output = Path(scratch) / 'tree.nbt'
            with fixture_world(args, 'Jungle Dark Oak Geometry', render=True, pack=args.pack, env={
                'HORIZON_NO_AUDIO': '1', 'CREATE_TREE_FERTILIZER_TRACE_SEED': str(seed),
                'CREATE_TEST_SCHEMATIC_CAPTURE': str(output),
            }) as world:
                world.commands((
                    '/fill -2 169 10 22 169 34 minecraft:dirt',
                    '/fill -2 170 10 22 210 34 minecraft:air',
                    '/tp @s 7.5 170 22.5', '/gamemode survival',
                    f'/setblock 10 170 22 minecraft:{species}_sapling[stage=0]',
                    f'/item replace entity @s hotbar.0 with {ITEM} 2',
                ))
                if scenario == 'giant_obstacles':
                    world.commands(('/setblock 10 172 22 minecraft:bedrock',
                                    '/setblock 11 173 22 minecraft:stone',
                                    '/setblock 11 175 19 minecraft:stone'))
                if scenario in ('giant', 'giant_obstacles'):
                    world.commands((f'/setblock 11 170 22 minecraft:{species}_sapling[stage=0]',
                                    f'/setblock 10 170 23 minecraft:{species}_sapling[stage=0]',
                                    f'/setblock 11 170 23 minecraft:{species}_sapling[stage=0]'))
                if scenario.startswith('corner_'):
                    dx = -1 if scenario in ('corner_negneg', 'corner_negpos') else 1
                    dz = -1 if scenario in ('corner_negneg', 'corner_posneg') else 1
                    world.commands((f'/setblock {10 + dx} 170 22 minecraft:{species}_sapling[stage=0]',
                                    f'/setblock 10 170 {22 + dz} minecraft:{species}_sapling[stage=0]',
                                    f'/setblock {10 + dx} 170 {22 + dz} minecraft:{species}_sapling[stage=0]'))
                    if dx < 0:
                        world.command('/tp @s 13.5 170 22.5')
                if scenario in ('partial_air', 'partial_mixed'):
                    world.commands((f'/setblock 11 170 22 minecraft:{species}_sapling[stage=0]',
                                    f'/setblock 10 170 23 minecraft:{species}_sapling[stage=0]'))
                    if scenario == 'partial_mixed':
                        world.command('/setblock 11 170 23 minecraft:birch_sapling[stage=0]')
                mp.until('fertilizer delivery', lambda: mp.count(world, ITEM) == 2)
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
                    world.call('create-test-schematic-capture', -2, 169, 10, 22, 210, 34)
                    tag = read_nbt(output)
                    actual = {}
                    for block in tag['blocks']:
                        x, y, z = block['pos']
                        state = tag['palette'][block['state']]
                        name = state['id']
                        properties = state.get('properties', {})
                        if name != 'minecraft:air':
                            suffix = '[' + ','.join(f'{k}={v}' for k, v in sorted(properties.items())) + ']' if properties else ''
                            actual[(x - 12, y - 1, z - 12)] = name + suffix
                    reference = {(x, y, z): state for (t, x, y, z), state in expected.items() if t == tick}
                    differences = [(pos, reference.get(pos), actual.get(pos))
                                   for pos in sorted(reference.keys() | actual.keys())
                                   if reference.get(pos) != actual.get(pos)]
                    remaining = mp.count(world, ITEM)
                    print(f'{species} {scenario} seed {seed}, tick {tick}: {len(reference)} Java blocks, '
                          f'{len(actual)} Horizon blocks, {len(differences)} differences, '
                          f'{remaining} fertilizer remaining', flush=True)
                    if differences or remaining != 1:
                        failures.append((seed, tick, remaining, differences))
    if failures:
        raise AssertionError(f'Java/Horizon tree differences: {failures}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--cases', nargs='+', type=lambda x: (x.split(':')[0], x.split(':')[1], int(x.split(':')[2])),
                        default=[('jungle', 'giant', 13), ('jungle', 'giant', 4096),
                                 ('dark_oak', 'giant', 13), ('dark_oak', 'giant', 4096),
                                 ('jungle', 'single', 13), ('jungle', 'single', 4096),
                                 ('jungle', 'giant_obstacles', 13), ('dark_oak', 'giant_obstacles', 13),
                                 ('jungle', 'corner_negneg', 4096), ('jungle', 'corner_negpos', 4096),
                                 ('jungle', 'corner_posneg', 4096), ('dark_oak', 'corner_negneg', 4096),
                                 ('dark_oak', 'corner_negpos', 4096), ('dark_oak', 'corner_posneg', 4096),
                                 ('jungle', 'partial_air', 13), ('jungle', 'partial_mixed', 13),
                                 ('dark_oak', 'partial_air', 13), ('dark_oak', 'partial_mixed', 13)])
    run(parser.parse_args())
