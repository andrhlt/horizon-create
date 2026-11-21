#!/usr/bin/env python3
"""Compare real Super Glue clicks and saved region to pinned Create Java."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')


def run(args):
    with (ROOT / 'fixtures/super_glue_selection-java.csv').open(newline='') as f:
        expected = next(csv.DictReader(f))
    with fixture_world(args, 'SuperGlueSelection', render=True, pack=args.pack,
                       env={'HORIZON_NO_AUDIO': '1'}) as world:
        world.commands((
            '/fill 2 169 16 10 169 23 minecraft:stone',
            '/fill 2 170 16 10 175 23 minecraft:air',
            '/fill 5 170 20 7 170 20 minecraft:stone',
            '/gamemode survival @s',
            '/tp @s 6.5 170 17.5',
            '/item replace entity @s hotbar.0 with create:super_glue',
        ))
        mp.until('glue held', lambda: mp.count(world, 'create:super_glue') == 1)
        def click(x):
            world.call('look-at', x + .5, 170.5, 20.5)
            mp.until('selected stone targeted', lambda: (world.call('looking-at').get('block') or {}).get('pos') == [x, 170, 20])
            world.call('mouse', 'right', 'click')
            world.call('wait', 3)
        click(5)
        first = world.command('/data get entity @s SelectedItem')
        assert 'create:super_glue_start' in first, first
        click(7)
        item = world.command('/data get entity @s SelectedItem')
        region = world.command('/data get entity @e[type=minecraft:marker,limit=1]')
        print('ITEM', item, 'REGION', region, flush=True)
        assert f'"minecraft:damage": {expected["damage"]}' in item, item
        assert 'create:super_glue_start' not in item, item
        assert 'CreateSuperGlue: 1b' in region, region
        assert expected['from'] in region and expected['to'] in region, region
        world.command('/save-all')
        world.stop()
        world.open()
        persisted = world.command('/data get entity @e[type=minecraft:marker,limit=1]')
        assert 'CreateSuperGlue: 1b' in persisted, persisted
        assert expected['from'] in persisted and expected['to'] in persisted, persisted
        for damage, z in ((97, 24), (98, 28)):
            world.commands((
                f'/fill 2 169 {z-4} 10 169 {z+1} minecraft:stone',
                f'/fill 2 170 {z-4} 10 175 {z+1} minecraft:air',
                f'/fill 5 170 {z} 7 170 {z} minecraft:stone',
                f'/tp @s 6.5 170 {z-2.5}',
                f'/item replace entity @s hotbar.0 with create:super_glue[minecraft:damage={damage}]',
            ))
            for x in (5, 7):
                world.call('look-at', x + .5, 170.5, z + .5)
                mp.until('worn glue target', lambda: (world.call('looking-at').get('block') or {}).get('pos') == [x, 170, z])
                world.call('mouse', 'right', 'click')
                world.call('wait', 3)
            mp.until('worn glue breaks', lambda: mp.count(world, 'create:super_glue') == 0)
            region = world.command(f'/data get entity @e[type=minecraft:marker,x=6.5,y=170,z={z+.5},distance=..2,limit=1]')
            assert 'CreateSuperGlue: 1b' in region, (damage, region)
        # Java's availability check still hurts the selected stack, then the
        # real consumption call searches the rest of inventory if it broke.
        world.commands((
            '/fill 2 169 32 10 169 33 minecraft:stone',
            '/fill 2 170 32 10 175 33 minecraft:air',
            '/fill 5 170 32 7 170 32 minecraft:stone',
            '/tp @s 6.5 170 29.5',
            '/item replace entity @s hotbar.0 with create:super_glue[minecraft:damage=99]',
            '/item replace entity @s hotbar.1 with create:super_glue',
        ))
        mp.until('near-broken and spare glue held', lambda: mp.count(world, 'create:super_glue') == 2)
        for x in (5, 7):
            world.call('look-at', x + .5, 170.5, 32.5)
            mp.until('spare-charge target', lambda: (world.call('looking-at').get('block') or {}).get('pos') == [x, 170, 32])
            world.call('mouse', 'right', 'click')
            world.call('wait', 3)
        region = world.command('/data get entity @e[type=minecraft:marker,x=6.5,y=170,z=32.5,distance=..2,limit=1]')
        assert 'CreateSuperGlue: 1b' in region, region
        inventory = world.command('/data get entity @s Inventory')
        print('SPARE_GLUE_INVENTORY', inventory, flush=True)
        assert 'Slot: 0b' not in inventory, inventory
        assert 'Slot: 1b' in inventory and 'minecraft:damage": 1' in inventory, inventory
        # Sneaking with an active selection cancels it without charge or glue.
        world.commands((
            '/fill 5 169 36 9 169 44 minecraft:stone',
            '/fill 5 170 40 7 175 40 minecraft:air',
            '/fill 5 170 40 7 170 40 minecraft:stone',
            '/tp @s 6.5 170 37.5',
            '/item replace entity @s hotbar.0 with create:super_glue',
        ))
        for x in (5,):
            world.call('look-at', x + .5, 170.5, 40.5)
            mp.until('cancellation start target', lambda: (world.call('looking-at').get('block') or {}).get('pos') == [x, 170, 40])
            world.call('mouse', 'right', 'click')
            world.call('wait', 3)
        world.call('key', 'shift', 'down')
        world.call('wait', 3)
        world.call('look-at', 7.5, 170.5, 40.5)
        mp.until('cancellation end target', lambda: (world.call('looking-at').get('block') or {}).get('pos') == [7, 170, 40])
        world.call('mouse', 'right', 'click')
        world.call('wait', 3)
        world.call('key', 'shift', 'up')
        item = world.command('/data get entity @s SelectedItem')
        region = world.command('/data get entity @e[type=minecraft:marker,x=6.5,y=170,z=40.5,distance=..2,limit=1]')
        print('CANCEL_RESULT', item, region, flush=True)
        assert 'create:super_glue_start' not in item and 'minecraft:damage' not in item, item
        assert 'No entity was found' in region, region

        # Two separately selected connected regions may share a block.
        world.commands((
            '/fill 5 169 37 9 169 44 minecraft:stone',
            '/fill 5 170 44 9 170 44 minecraft:stone',
            '/fill 5 171 44 9 175 44 minecraft:air',
            '/tp @s 6.5 170 41.5',
        ))
        world.call('wait', 3)
        for a, b in ((5, 7), (7, 8)):
            world.command('/item replace entity @s hotbar.0 with create:super_glue')
            for x in (a, b):
                world.call('look-at', x + .5, 170.5, 44.5)
                mp.until('overlap target', lambda: (world.call('looking-at').get('block') or {}).get('pos') == [x, 170, 44])
                world.call('mouse', 'right', 'click')
                world.call('wait', 3)
            world.command('/tp @s 6.5 170 41.5')
            world.call('wait', 3)
        for x in (6.5, 8.0):
            region = world.command(f'/data get entity @e[type=minecraft:marker,x={x},y=170,z=44.5,distance=..2,limit=1]')
            assert 'CreateSuperGlue: 1b' in region, (x, region)
        world.call('look-at', 5.5, 170.5, 44.5)
        mp.until('glued block targeted for removal', lambda: (world.call('looking-at').get('block') or {}).get('pos') == [5, 170, 44])
        world.call('mouse', 'left', 'click')
        world.call('wait', 3)
        removed = world.command('/data get entity @e[type=minecraft:marker,x=6.5,y=170,z=44.5,distance=..0.1,limit=1]')
        retained = world.command('/data get entity @e[type=minecraft:marker,x=8,y=170,z=44.5,distance=..0.1,limit=1]')
        block = world.call('block', 5, 170, 44)['block']
        assert 'No entity was found' in removed, removed
        assert 'CreateSuperGlue: 1b' in retained, retained
        assert block == 'minecraft:stone', block
    print('Super Glue selection, charge fallback, cancellation, overlapping regions, removal and persistence matched.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
