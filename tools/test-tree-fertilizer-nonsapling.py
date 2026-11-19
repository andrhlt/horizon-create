#!/usr/bin/env python3
"""Compare fertilizer use on bonemealable non-saplings against Java.

Apply java-tree-fertilizer-nonsapling-trace.patch to the pinned Java clone and
set TREE_FIXTURE_SPECIES to each case. Remove the disposable clone's run/world
before every offline game test. Random ticks are disabled in both runtimes.
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
    with (ROOT / 'fixtures/tree_fertilizer_nonsapling-java.csv').open() as source:
        rows = list(csv.DictReader(source))
    failures = []
    for species in args.cases:
        reference = {(int(r['tick']), int(r['x']), int(r['y']), int(r['z'])): r['state']
                     for r in rows if r['species'] == species}
        assert reference, species
        outcomes = {(r['java_result'], int(r['java_remaining'])) for r in rows if r['species'] == species}
        assert outcomes == {('PASS', 2)}, (species, outcomes)
        java_remaining = next(iter(outcomes))[1]
        with TemporaryDirectory(prefix='fertilizer-nonsapling-') as scratch:
            output = Path(scratch) / 'world.nbt'
            with fixture_world(args, 'Fertilizer Non Sapling', render=True, pack=args.pack, env={
                'HORIZON_NO_AUDIO': '1', 'CREATE_TEST_SCHEMATIC_CAPTURE': str(output),
            }) as world:
                soil = {'crimson_fungus': 'crimson_nylium', 'warped_fungus': 'warped_nylium'}.get(species, 'dirt')
                world.commands((
                    '/fill -2 169 10 22 169 34 minecraft:dirt',
                    '/fill -2 170 10 22 194 34 minecraft:air',
                    '/gamerule randomTickSpeed 0', '/tp @s 10.5 170 25.5', '/gamemode survival',
                ))
                if soil != 'dirt':
                    world.command(f'/setblock 10 169 22 minecraft:{soil}')
                world.command(f'/setblock 10 170 22 minecraft:{species}')
                world.command(f'/item replace entity @s hotbar.0 with {ITEM} 2')
                mp.until('fertilizer delivery', lambda: mp.count(world, ITEM) == 2)
                world.call('select', ITEM)
                before = world.call('block', 10, 170, 22)['block']
                assert before == 'minecraft:' + species, (species, before)
                hit = False
                for x in (10.5, 10.35, 10.65, 10.25, 10.75):
                    for z in (22.5, 22.35, 22.65, 22.25, 22.75):
                        world.call('look-at', x, 170.2, z)
                        if (world.call('looking-at').get('block') or {}).get('pos') == [10, 170, 22]:
                            hit = True
                            break
                    if hit:
                        break
                assert hit, f'Could not target {species}'
                start = world.clock()
                world.call('mouse', 'right', 'click')
                world.call('wait', 4)
                assert world.clock() == start
                for tick in range(4):
                    if tick:
                        world.step_to(start + tick)
                    world.call('create-test-schematic-capture', -2, 170, 10, 22, 194, 34)
                    tag = read_nbt(output)
                    actual = {}
                    for block in tag['blocks']:
                        x, y, z = block['pos']
                        state = tag['palette'][block['state']]
                        name, props = state['id'], state.get('properties', {})
                        if name != 'minecraft:air':
                            suffix = '[' + ','.join(f'{k}={v}' for k, v in sorted(props.items())) + ']' if props else ''
                            actual[(x - 12, y, z - 12)] = name + suffix
                    actual[(0, -1, 0)] = world.call('block', 10, 169, 22)['state']
                    expected = {(x, y, z): state for (t, x, y, z), state in reference.items() if t == tick}
                    differences = [(p, expected.get(p), actual.get(p)) for p in sorted(expected.keys() | actual.keys()) if expected.get(p) != actual.get(p)]
                    remaining = mp.count(world, ITEM)
                    print(f'{species} tick {tick}: Java {len(expected)}, Horizon {len(actual)}, differences {len(differences)}, fertilizer {remaining}', flush=True)
                    if differences or remaining != java_remaining:
                        failures.append((species, tick, differences[:20], remaining))
    if failures:
        raise AssertionError(failures)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--cases', nargs='+',
                        default=['brown_mushroom', 'red_mushroom', 'crimson_fungus',
                                 'warped_fungus', 'bamboo_sapling'])
    run(parser.parse_args())
