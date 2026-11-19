#!/usr/bin/env python3
"""Exercise conversion, placement and package transport for the Repackager."""
import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

crafting = import_module('test-survival-crafting')
packager = import_module('test-packager-redstone')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--pack', type=Path)
    args = parser.parse_args()
    with fixture_world(args, 'RepackagerConversions', render=True, pack=args.pack) as world:
        world.commands(('/gamemode survival', '/item replace entity @s hotbar.0 with create:packager'))
        world.call('wait', 3)
        world.call('open-inventory')
        for source, target in (('create:packager', 'create:repackager'),
                               ('create:repackager', 'create:packager')):
            crafting.distribute(world, crafting.inventory_slot(world, source), (100,))
            crafting.craft(world, target, 1)
        print('Both 1:1 conversion recipes succeeded.', flush=True)

    with fixture_world(args, 'RepackagerGameplay', render=True, pack=args.pack) as world:
        world.commands(('/fill 5 104 -15 13 104 -9 minecraft:smooth_stone',
                        '/fill 5 105 -15 13 109 -9 minecraft:air',
                        '/setblock 7 105 -12 minecraft:barrel', '/tp @s 10.5 105 -11.5',
                        '/item replace entity @s hotbar.0 with create:repackager'))
        world.call('wait', 3)
        world.call('select', 'create:repackager')
        world.call('wait', 3)
        world.call('interact', 8, 104, -12, 'up')
        world.call('wait', 3)
        placed = world.call('block', 8, 105, -12)
        assert 'facing=east' in placed['state'], placed
        world.command('/item replace entity @s hotbar.0 with create:cardboard_package_12x12')
        world.call('wait', 3)
        world.call('select', 'create:cardboard_package_12x12')
        world.call('wait', 3)
        world.call('look-at', 8.98, 105.5, -11.5)
        world.call('mouse', 'right', 'click')
        world.call('wait', 3)
        barrel = packager.block_data(world, (7, 105, -12))
        assert 'create:cardboard_package_12x12' in barrel, barrel
        for _ in range(25):
            world.step_to(world.clock() + 1)
        world.command('/setblock 8 105 -11 minecraft:redstone_block')
        state = packager.block_data(world, (8, 105, -12))
        barrel = packager.block_data(world, (7, 105, -12))
        assert 'HeldBox:' in state and 'create:cardboard_package_12x12' in state, state
        assert 'create:cardboard_package_12x12' not in barrel, barrel
        print('Placement faced away from the barrel; package ingress and redstone passthrough succeeded.', flush=True)


if __name__ == '__main__':
    main()
