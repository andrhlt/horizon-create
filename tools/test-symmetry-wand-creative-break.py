#!/usr/bin/env python3
"""Compare a creative Wand break with a different mirrored material to Java."""
import argparse
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')
wand = import_module('test-symmetry-wand-plane')
ITEM = 'create:wand_of_symmetry'
PICK = 'minecraft:iron_pickaxe'

def run(args):
    with (ROOT / 'fixtures/symmetry_wand_break-java.csv').open() as source:
        java = {row['case']: row for row in csv.DictReader(source)}['creative_mismatch']
    with fixture_world(args, 'SymmetryCreativeBreak', pack=args.pack) as host:
        host.commands((
            '/fill 5 169 17 17 169 29 minecraft:stone',
            '/fill 5 170 17 17 174 29 minecraft:air',
            '/tp @s 10.5 170 25.5',
            f'/item replace entity @s hotbar.0 with {ITEM}[minecraft:custom_data={{marker:17}}]',
            f'/item replace entity @s hotbar.1 with {PICK}',
            '/tick unfreeze',
        ))
        mp.until('the Wand', lambda: mp.count(host, ITEM) == 1)
        wand.activation(host, host, '@s', (10, 169, 22), 0, (10, 170, 22))
        host.commands(('/setblock 10 171 24 minecraft:stone', '/setblock 10 171 20 minecraft:dirt'))
        host.call('select', PICK)
        host.call('break', 10, 171, 24, '--timeout', 20)
        mp.until('the original block to break', lambda: host.call('block', 10, 171, 24)['block'] == 'minecraft:air')
        mp.until('the mirrored block', lambda: host.call('block', 10, 171, 20)['block'] == java['mirror_after'])
        assert java['mirror_after'] == 'minecraft:air' and java['drop_count'] == '0' and java['tool_damage'] == '0'
        drops = host.call('entities', 32, 'minecraft:item')['entities']
        assert not drops, drops
        selected = host.command('/data get entity @s SelectedItem')
        assert 'minecraft:damage' not in selected or '"minecraft:damage": 0' in selected, selected
    print('Creative stone break removed mirrored dirt without drops or tool wear, matching Java.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument('--pack', type=lambda value: Path(value).resolve())
    run(parser.parse_args())
