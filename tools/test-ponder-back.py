#!/usr/bin/env python3
"""Return from Shaft Ponder to inventory with Java Backspace and the back button."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')


def run(args):
    with TemporaryDirectory(prefix='hc-ponder-frame-') as scratch:
        image = Path(scratch) / 'inventory.png'
        with fixture_world(args, 'PonderBack', render=True, pack=args.pack,
                           env={'HORIZON_NO_AUDIO': '1', 'CREATE_PONDER_TRACE': '1'}) as world:
            world.commands((
                '/gamemode survival @s',
                '/clear @s',
                '/item replace entity @s hotbar.0 with create:shaft',
                '/item replace entity @s hotbar.1 with minecraft:stone',
                '/setblock 5 170 20 minecraft:diamond_block',
            ))
            before = world.call('inventory')['counts']
            world.call('key', 'e', 'tap')
            mp.until('inventory open', lambda: world.call('screen')['screen'] == 'inventory')
            world.call('wait', 3)
            button = world.call('screen')['recipe_book']['targets'][0]
            left, top = button[0] - 104, button[1] - 61
            def hover(slot):
                world.call('scroll-at', left + 16 + slot * 18, top + 150, 0)
                world.call('wait', 3)
            hover(1)
            world.call('key', 'w', 'down')
            world.call('wait', 20)
            world.call('key', 'w', 'up')
            assert world.call('screen')['screen'] == 'inventory'
            hover(0)
            world.call('key', 'w', 'down')
            try:
                mp.until('shaft Ponder opens', lambda: world.call('screen')['screen'] == 'mod')
            finally:
                world.call('key', 'w', 'up')
            log = world.socket.parent / 'ctl.log'
            def text():
                return log.read_text(errors='replace') if log.exists() else ''
            mp.until('scene geometry', lambda: 'CREATE_PONDER render vertices ' in text())
            world.call('key', 'backspace', 'tap')
            mp.until('Backspace returns to inventory', lambda: world.call('screen')['screen'] == 'inventory')
            assert world.call('inventory')['counts'] == before
            hover(0)
            world.call('key', 'w', 'down')
            try:
                mp.until('Ponder reopens', lambda: world.call('screen')['screen'] == 'mod')
            finally:
                world.call('key', 'w', 'up')
            world.call('click-at', 40, 35)
            mp.until('back button returns to inventory', lambda: world.call('screen')['screen'] == 'inventory')
            hover(0)
            world.call('key', 'w', 'down')
            try:
                mp.until('Ponder opens a third time', lambda: world.call('screen')['screen'] == 'mod')
            finally:
                world.call('key', 'w', 'up')
            world.call('key', 'escape', 'tap')
            mp.until('Escape returns to gameplay', lambda: world.call('screen')['screen'] == 'playing')
            assert world.call('inventory')['counts'] == before
            assert 'minecraft:diamond_block' in world.call('block', 5, 170, 20)['state']
    print('Ponder Backspace and back button return to inventory; Escape closes to gameplay.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
