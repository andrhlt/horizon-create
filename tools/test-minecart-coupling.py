#!/usr/bin/env python3
"""Exercise initial survival Minecart Coupling selection and wrench removal."""
import argparse
import re
from pathlib import Path
from fixture_world import fixture_world

def run(args):
    with fixture_world(args, 'MinecartCoupling', pack=args.pack, render=True) as world:
        world.commands((
            '/fill 4 169 20 16 169 28 minecraft:stone',
            '/setblock 8 170 24 minecraft:rail[shape=north_south]',
            '/setblock 11 170 24 minecraft:rail[shape=north_south]',
            '/summon minecraft:minecart 8.5 170.0625 24.5 {Tags:["coupling_a"]}',
            '/summon minecraft:minecart 11.5 170.0625 24.5 {Tags:["coupling_b"]}',
            '/gamemode survival',
            '/item replace entity @s hotbar.0 with create:minecart_coupling 2',
            '/item replace entity @s hotbar.1 with create:wrench',
            '/tp @s 8.5 170 22.5',
        ))
        def click(x):
            world.command(f'/tp @s {x} 170 22.5')
            world.call('look-at', x, 170.2, 24.5)
            world.call('wait', 4)
            world.call('mouse', 'right', 'click')
            world.call('wait', 3)
        def inventory(): return world.command('/data get entity @s Inventory')
        carts = [world.command(f'/data get entity @e[type=minecraft:minecart,tag={tag},limit=1] UUID') for tag in ('coupling_a', 'coupling_b')]
        uuids = [re.search(r'\[I;[^]]+\]', cart).group() for cart in carts]
        world.call('select', 'create:minecart_coupling')
        click(8.5)
        if 'count: 2' not in inventory(): raise RuntimeError('First selection consumed a coupling')
        click(11.5)
        held = inventory()
        link = world.command('/data get entity @e[type=minecraft:marker,tag=create_minecart_coupling,limit=1] CreateMinecartCoupling')
        if 'count: 1' not in held or 'Length: 3.0f' not in link or 'A: [I;' not in link or 'B: [I;' not in link:
            raise RuntimeError(f'Pair was not created: {held}; {link}')
        if not all(uuid in link for uuid in uuids): raise RuntimeError(f'Pair did not name both carts: {link}; {uuids}')
        world.restart()
        restored = world.command('/data get entity @e[type=minecraft:marker,tag=create_minecart_coupling,limit=1] CreateMinecartCoupling')
        if not all(uuid in restored for uuid in uuids) or 'Length: 3.0f' not in restored: raise RuntimeError(f'Pair did not survive reload: {restored}')
        world.call('select', 'create:wrench')
        click(8.5)
        held = inventory()
        if 'count: 2' not in held or 'Test passed' in world.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]'):
            raise RuntimeError(f'Wrench did not remove and return the coupling: {held}')
        world.command('/tp @e[type=minecraft:minecart,tag=coupling_b,limit=1] 44.5 170.0625 24.5')
        world.call('select', 'create:minecart_coupling')
        click(8.5)
        click(8.5)
        if 'count: 2' not in inventory(): raise RuntimeError('Repeated selection consumed a coupling')
        click(44.5)
        if 'count: 2' not in inventory() or 'Test passed' in world.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]'):
            raise RuntimeError('Out-of-range coupling consumed an item or created a link')
    print('Survival clicks created and removed a three-block cart pair.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'): parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument('--pack', type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
