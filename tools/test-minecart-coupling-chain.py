#!/usr/bin/env python3
"""Select a three-cart chain without consuming the attempted closing loop."""
import argparse
from pathlib import Path
from fixture_world import fixture_world

def run(args):
    with fixture_world(args, 'CouplingChain', pack=args.pack, render=True) as w:
        w.commands(('/fill 4 169 20 18 169 28 minecraft:stone',
                    '/fill 4 170 24 18 170 24 minecraft:rail[shape=east_west]',
                    '/summon minecraft:minecart 8.5 170.0625 24.5 {Tags:["chain_a"]}',
                    '/summon minecraft:minecart 11.5 170.0625 24.5 {Tags:["chain_b"]}',
                    '/summon minecraft:minecart 14.5 170.0625 24.5 {Tags:["chain_c"]}',
                    '/gamemode survival','/item replace entity @s hotbar.0 with create:minecart_coupling 3','/item replace entity @s hotbar.1 with create:wrench','/tp @s 8.5 170 22.5'))
        def click(x):
            w.command(f'/tp @s {x} 170 22.5');w.call('look-at',x,170.2,24.5);w.call('wait',4);w.call('mouse','right','click');w.call('wait',3)
        w.call('select','create:minecart_coupling')
        for x in (8.5,11.5,11.5,14.5): click(x)
        inventory=w.command('/data get entity @s SelectedItem')
        markers=w.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]')
        if 'count: 1' not in inventory or 'Count: 2' not in markers:
            raise RuntimeError(f'Expected a two-link chain: {inventory}; {markers}')
        for x in (14.5,8.5): click(x)
        if 'count: 1' not in w.command('/data get entity @s SelectedItem') or 'Count: 2' not in w.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]'):
            raise RuntimeError('Closing loop was accepted or consumed an item')
        w.restart()
        if 'Count: 2' not in w.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]'):
            raise RuntimeError('Chain did not survive restart')
        w.call('select','create:wrench');click(11.5)
        if 'count: 3' not in w.command('/data get entity @s Inventory') or 'Test passed' in w.command('/execute if entity @e[type=minecraft:marker,tag=create_minecart_coupling]'):
            raise RuntimeError('Wrench did not remove both middle-cart links and refund two items')
    print('Three carts formed a persistent chain, rejected a loop, and refunded both links.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'):p.add_argument(name,type=lambda x:Path(x).resolve(strict=True))
    p.add_argument('--pack',type=lambda x:Path(x).resolve(strict=True));run(p.parse_args())
