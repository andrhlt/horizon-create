#!/usr/bin/env python3
"""Replay fertilizer use on original birch and cherry saplings."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT, fixture_world

multiplayer = import_module('test-multiplayer')
ITEM = 'create:tree_fertilizer'


def run(args):
    with (ROOT / 'fixtures/tree_fertilizer_species-java.csv').open() as source:
        rows = list(csv.DictReader(source))
    with fixture_world(args, 'Fertilizer Species', render=True, pack=args.pack,
                       env={'HORIZON_NO_AUDIO': '1'}) as world:
        for row in rows:
            for command in (
                '/fill 6 169 20 14 169 28 minecraft:dirt',
                '/fill 6 170 20 14 185 28 minecraft:air',
                '/tp @s 10.5 170 25.5',
                '/gamemode survival',
                f'/setblock 10 170 22 {row["sapling"]}[stage=0]',
                f'/item replace entity @s hotbar.0 with {ITEM} 2',
            ):
                world.call('command', command)
            multiplayer.until('fertilizer delivery', lambda: multiplayer.count(world, ITEM) == 2)
            world.call('select', ITEM)
            world.call('look-at', 10.5, 170.35, 22.5)
            multiplayer.until('sapling target', lambda:
                              (world.call('looking-at').get('block') or {}).get('pos') == [10, 170, 22])
            world.call('mouse', 'right', 'click')
            world.call('wait', 4)
            base = world.call('block', 10, 170, 22)['block']
            above = world.call('block', 10, 171, 22)['block']
            remaining = multiplayer.count(world, ITEM)
            compare_above = row['sapling'] != 'minecraft:acacia_sapling'
            if (base != row['base'] or remaining != int(row['remaining'])
                    or (compare_above and above != row['above'])):
                raise AssertionError(f'{row["sapling"]}: Horizon {base, above, remaining}, Java {row}')
            print(f'{row["sapling"]}: base and consumption matched Java'
                  + ('; above-base trunk also matched.' if compare_above else '.'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
