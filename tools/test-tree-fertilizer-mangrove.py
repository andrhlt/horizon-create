#!/usr/bin/env python3
"""Compare full mangrove growth and hanging propagule use against Java.

Apply java-tree-fertilizer-mangrove-trace.patch to the pinned Java clone;
set TREE_FIXTURE_SPECIES=mangrove, ACACIA_FIXTURE_ENV=mud, hanging, hanging_immature, waterlogged or pool and
ACACIA_FIXTURE_SEED to the fixture seed; set TREE_PROPAGULE_AGE=0 for hanging_immature. Remove the disposable clone's run/world
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
    with (ROOT / 'fixtures/tree_fertilizer_mangrove_geometry-java.csv').open() as source:
        rows = list(csv.DictReader(source))
    failures = []
    for scenario, seed in args.cases:
        expected = {(int(r['tick']), int(r['x']), int(r['y']), int(r['z'])): r['state']
                    for r in rows if r['scenario'] == scenario and int(r['seed']) == seed}
        if not expected:
            raise ValueError((scenario, seed))
        with TemporaryDirectory(prefix='mangrove-capture-') as scratch:
            output = Path(scratch) / 'tree.nbt'
            with fixture_world(args, 'Mangrove Geometry', render=True, pack=args.pack, env={
                'HORIZON_NO_AUDIO': '1', 'CREATE_TREE_FERTILIZER_TRACE_SEED': str(seed),
                'CREATE_TEST_SCHEMATIC_CAPTURE': str(output),
            }) as world:
                world.commands((
                    '/fill -2 166 10 22 169 34 minecraft:dirt',
                    '/fill -2 170 10 22 210 34 minecraft:air',
                    '/tp @s 10.5 170 25.5', '/gamemode survival',
                    f'/item replace entity @s hotbar.0 with {ITEM} 2',
                ))
                if scenario in ('mud', 'waterlogged', 'pool'):
                    world.command('/setblock 10 169 22 minecraft:mud')
                else:
                    world.command('/setblock 10 171 22 minecraft:mangrove_leaves[persistent=true]')
                if scenario == 'pool':
                    world.command('/fill 9 170 21 11 170 23 minecraft:water')
                hanging = 'true' if scenario.startswith('hanging') else 'false'
                age = 0 if scenario == 'hanging_immature' else 4
                waterlogged = 'true' if scenario in ('waterlogged', 'pool') else 'false'
                world.command(f'/setblock 10 170 22 minecraft:mangrove_propagule[age={age},hanging={hanging},stage=1,waterlogged={waterlogged}]')
                mp.until('fertilizer delivery', lambda: mp.count(world, ITEM) == 2)
                if scenario == 'hanging_immature':
                    world.command('/tp @s 10.5 170 26.5')
                world.call('select', ITEM)
                world.call('look-at', 10.5, 170.9 if age == 0 else 170.5, 22.5)
                mp.until('propagule target', lambda:
                         (world.call('looking-at').get('block') or {}).get('pos') == [10, 170, 22])
                start = world.clock()
                world.call('mouse', 'right', 'click')
                world.call('wait', 4)
                assert world.clock() == start, 'Frozen game advanced during use'
                for tick in range(4):
                    if tick:
                        world.step_to(start + tick)
                    world.call('create-test-schematic-capture', -2, 166, 10, 22, 210, 34)
                    tag = read_nbt(output)
                    actual = {}
                    for block in tag['blocks']:
                        x, y, z = block['pos']
                        state = tag['palette'][block['state']]
                        name, properties = state['id'], state.get('properties', {})
                        if name != 'minecraft:air':
                            suffix = '[' + ','.join(f'{k}={v}' for k, v in sorted(properties.items())) + ']' if properties else ''
                            actual[(x - 12, y - 4, z - 12)] = name + suffix
                    ref = {(x, y, z): state for (t, x, y, z), state in expected.items() if t == tick}
                    diff = [(pos, ref.get(pos), actual.get(pos)) for pos in sorted(ref.keys() | actual.keys()) if ref.get(pos) != actual.get(pos)]
                    remaining = mp.count(world, ITEM)
                    print(f'{scenario} seed {seed} tick {tick}: Java {len(ref)} Horizon {len(actual)} differences {len(diff)} remaining {remaining}', flush=True)
                    if diff or remaining != (2 if scenario.startswith('hanging') else 1):
                        failures.append((scenario, seed, tick, remaining, diff[:20]))
    if failures:
        raise AssertionError(failures)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--cases', nargs='+', type=lambda x: (x.split(':')[0], int(x.split(':')[1])),
                        default=[('mud', 13), ('mud', 4096), ('mud', 2048), ('mud', 2), ('hanging', 13), ('waterlogged', 13), ('hanging_immature', 13), ('pool', 13)])
    run(parser.parse_args())
