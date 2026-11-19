#!/usr/bin/env python3
"""Exercise Schematic Table crafting and player-facing placement."""
import argparse
import time
from importlib import import_module
from pathlib import Path
from fixture_world import fixture_world

machine = import_module('test-machine-crafting')
mp = import_module('test-multiplayer')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument('--pack', type=Path)
    args = parser.parse_args()
    with fixture_world(args, 'Schematic-table', render=True, pack=args.pack) as world:
        world.commands((
            '/fill 4 169 18 16 169 28 minecraft:smooth_stone',
            '/setblock 12 170 24 minecraft:crafting_table',
            '/tp @s 12.5 170 26.5', '/gamemode survival',
        ))
        machine.replay(world, {'recipe':'schematic_table','width':'3',
            'slots':'minecraft:oak_slab,minecraft:oak_slab,minecraft:oak_slab,_,minecraft:smooth_stone,_,_,minecraft:smooth_stone,_',
            'output':'create:schematic_table','count':'1','remainder':''})
        for position, expected in (((8.5,170,22.5),'south'), ((11.5,170,20.5),'east')):
            world.commands(('/setblock 8 170 20 minecraft:air',
                '/item replace entity @s weapon.mainhand with create:schematic_table',
                f'/tp @s {position[0]} {position[1]} {position[2]}'))
            mp.until('previous table removed', lambda: world.call('block', 8, 170, 20)['block'] == 'minecraft:air')
            mp.until('player position', lambda: tuple(world.call('state')['player']['position']) == position)
            mp.until('held table', lambda: (world.call('inventory')['held'] or {}).get('item') == 'create:schematic_table')
            world.call('look-at', 8.5, 169.98, 20.5)
            mp.until('placement target', lambda: (world.call('looking-at').get('block') or {}).get('pos') == [8, 169, 20])
            time.sleep(0.3)  # Let the server receive the player's new view direction.
            world.call('mouse', 'right', 'click')
            mp.until('table placement facing the player', lambda:
                     world.call('block', 8, 170, 20)['state'] == f'create:schematic_table[facing={expected}]')
        print('Schematic Table crafted and faced the player from two directions.')

if __name__ == '__main__':
    main()
