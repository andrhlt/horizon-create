#!/usr/bin/env python3
"""Headless survival crafting and placement checks for Track Observer."""
import argparse
from pathlib import Path
from importlib import import_module
from fixture_world import fixture_world

crafting = import_module('test-survival-crafting')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--pack', type=Path)
    args = parser.parse_args()
    with fixture_world(args, 'Track-observer', render=True, pack=args.pack, env={'HORIZON_NO_AUDIO':'1'}) as world:
        world.command('/gamemode survival')
        for plate in ('oak_pressure_plate', 'stone_pressure_plate', 'polished_blackstone_pressure_plate', 'heavy_weighted_pressure_plate', 'light_weighted_pressure_plate'):
            world.commands(('/item replace entity @s hotbar.0 with create:railway_casing', f'/item replace entity @s hotbar.1 with minecraft:{plate}'))
            world.call('open-inventory')
            crafting.distribute(world, 0, (100,))
            crafting.distribute(world, 1, (101,))
            crafting.craft(world, 'create:track_observer', 2)
            world.call('close')
            print('Crafted two observers with', plate, flush=True)
        world.commands(('/fill -2 111 -15 25 111 1 minecraft:smooth_stone', '/fill 1 112 -8 23 112 -8 create:track[shape=xo]', '/tp @s 9.5 113 -5.5 180 20', '/item replace entity @s hotbar.0 with create:track_observer 2'))
        for _ in range(7): world.step_to(world.clock()+1)
        world.call('select', 'create:track_observer')
        world.call('look-at', 9.5, 112.06, -7.5)
        world.call('mouse', 'right', 'click')
        world.call('wait', 3)
        selected = world.command('/data get entity @s SelectedItem')
        print('Selected:', selected, flush=True)
        assert 'create:track_targeting_item_selected_pos' in selected, selected
        world.command('/tp @s 9.5 112 -2.5 180 20')
        world.call('wait', 2)
        world.call('interact', 9, 111, -5, 'up')
        world.call('wait', 3)
        state = world.call('block', 9, 112, -5)['state']
        nbt = world.command('/data get block 9 112 -5')
        print('Placed:', state, nbt, flush=True)
        assert state.startswith('create:track_observer') and 'TargetTrack: [I; 0, 0, -3]' in nbt, (state, nbt)

        # Exercise the same two-click targeting flow on a diagonal rail.
        world.commands(('/setblock 16 112 -8 create:track[shape=pd]',
                        '/setblock 17 112 -7 create:track[shape=pd]',
                        '/item replace entity @s hotbar.0 with create:track_observer'))
        world.command('/tp @s 16.5 113 -4.5 180 20')
        world.call('wait', 2)
        world.call('select', 'create:track_observer')
        world.call('look-at', 16.5, 112.06, -7.5)
        world.call('mouse', 'right', 'click')
        world.call('wait', 3)
        assert 'create:track_targeting_item_selected_pos' in world.command('/data get entity @s SelectedItem')
        world.command('/tp @s 16.5 112 -2.5 180 20')
        world.call('wait', 2)
        world.call('interact', 16, 111, -5, 'up')
        world.call('wait', 3)
        diagonal = world.call('block', 16, 112, -5)['state']
        diagonal_nbt = world.command('/data get block 16 112 -5')
        print('Diagonal placement:', diagonal, diagonal_nbt, flush=True)
        assert diagonal.startswith('create:track_observer') and 'TargetTrack: [I; 0, 0, -3]' in diagonal_nbt, (diagonal, diagonal_nbt)
