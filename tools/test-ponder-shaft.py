#!/usr/bin/env python3
"""Open the real Shaft Ponder scene from inventory, play, replay, and close it."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')


def run(args):
    with TemporaryDirectory(prefix='hc-ponder-frame-') as scratch:
        image = Path(scratch) / 'inventory.png'
        with fixture_world(args, 'PonderShaft', render=True, pack=args.pack,
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
            world.call('wait', 75)
            world.call('screenshot', ROOT / '.local/ponder-shaft.png')
            recorded = text()
            for event in ('open tick 0 blocks 32', 'tick 5', 'tick 20', 'tick 25',
                          'tick 30', 'tick 35', 'tick 45', 'tick 65'):
                assert 'CREATE_PONDER ' + event in recorded, event
            marker = next(line for line in recorded.splitlines() if 'CREATE_PONDER render vertices ' in line)
            assert int(marker.rsplit(' ', 1)[1]) > 0, marker
            world.call('key', 'space', 'tap')
            world.call('key', 'r', 'tap')
            mp.until('scene replay', lambda: 'CREATE_PONDER replay tick 0' in text())
            if args.encasing:
                gui_height = top * 2 + 166
                world.call('click-at', 310, gui_height - 22)
                mp.until('encasing storyboard opens', lambda: 'CREATE_PONDER encasing open blocks 36' in text())
                world.call('wait', 43)
                world.call('screenshot', ROOT / '.local/ponder-encasing-controls.png')
                world.call('wait', 95)
                world.call('screenshot', ROOT / '.local/ponder-encasing.png')
                recorded = text()
                for tick in (20, 27, 37, 44, 54, 124):
                    assert f'CREATE_PONDER encasing tick {tick}' in recorded, tick
                world.call('key', 'left', 'tap')
                mp.until('relay storyboard returns', lambda: 'CREATE_PONDER relay open blocks 32' in text())
            world.call('key', 'escape', 'tap')
            mp.until('scene closed', lambda: world.call('screen')['screen'] != 'mod')
            assert world.call('inventory')['counts'] == before
            assert 'minecraft:diamond_block' in world.call('block', 5, 170, 20)['state']
    print('Shaft hover, scene timeline, model geometry, replay, and close passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--encasing', action='store_true', help='play the second Shaft storyboard')
    run(parser.parse_args())
