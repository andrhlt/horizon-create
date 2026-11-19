#!/usr/bin/env python3
"""Switching away from a selected cart cancels the coupling selection."""
import argparse
from pathlib import Path
from fixture_world import fixture_world

def run(args):
    with fixture_world(args, 'CouplingSelection', pack=args.pack, render=True) as world:
        world.commands(('/fill 4 169 20 16 169 28 minecraft:stone',
                        '/setblock 8 170 24 minecraft:rail[shape=north_south]',
                        '/setblock 11 170 24 minecraft:rail[shape=north_south]',
                        '/summon minecraft:minecart 8.5 170.0625 24.5 {Tags:["selection_a"]}',
                        '/summon minecraft:minecart 11.5 170.0625 24.5 {Tags:["selection_b"]}',
                        '/gamemode survival', '/item replace entity @s hotbar.0 with create:minecart_coupling 2',
                        '/item replace entity @s hotbar.1 with create:wrench', '/tp @s 8.5 170 22.5'))
        def click(x):
            world.command(f'/tp @s {x} 170 22.5');world.call('look-at',x,170.2,24.5);world.call('wait',4);world.call('mouse','right','click');world.call('wait',3)
        world.call('select','create:minecart_coupling');click(8.5)
        world.call('select','create:wrench');world.call('wait',5)
        world.call('select','create:minecart_coupling');click(11.5)
        inventory=world.command('/data get entity @s Inventory')
        marker=world.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]')
        if 'count: 2' not in inventory or 'Test passed' in marker:
            raise RuntimeError(f'Selection survived switching away: {inventory}; {marker}')
        click(8.5)
        if 'count: 1' not in world.command('/data get entity @s Inventory') or 'Test passed' not in world.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]'):
            raise RuntimeError('The new selection did not create a pair')
        world.call('select','create:wrench');click(8.5)
        world.command('/item replace entity @s weapon.offhand with create:minecart_coupling')
        world.call('select','create:minecart_coupling');click(8.5)
        world.call('select','create:wrench');world.call('wait',5)
        world.call('select','create:minecart_coupling');click(11.5)
        if 'Test passed' not in world.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]'):
            raise RuntimeError('Holding a coupling in the offhand failed to retain selection')
    print('Switching away canceled selection; holding a coupling in the offhand retained it.')

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'): p.add_argument(name,type=lambda x:Path(x).resolve(strict=True))
    p.add_argument('--pack',type=lambda x:Path(x).resolve(strict=True))
    run(p.parse_args())
