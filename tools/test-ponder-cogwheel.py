#!/usr/bin/env python3
"""Open the real Cogwheel Ponder scene from inventory, play, replay, and close it."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')


def run(args):
    with TemporaryDirectory(prefix='hc-ponder-frame-') as scratch:
        image = Path(scratch) / 'inventory.png'
        with fixture_world(args, 'PonderCogwheel', render=True, pack=args.pack,
                           env={'HORIZON_NO_AUDIO': '1', 'CREATE_PONDER_TRACE': '1'}) as world:
            world.commands((
                '/gamemode survival @s',
                '/clear @s',
                '/item replace entity @s hotbar.0 with create:cogwheel',
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
                mp.until('cogwheel Ponder opens', lambda: world.call('screen')['screen'] == 'mod')
            finally:
                world.call('key', 'w', 'up')
            log = world.socket.parent / 'ctl.log'
            def text():
                return log.read_text(errors='replace') if log.exists() else ''
            mp.until('scene geometry', lambda: 'CREATE_PONDER render vertices ' in text())
            world.call('wait', 220)
            world.call('screenshot', ROOT / '.local/ponder-cogwheel.png')
            recorded = text()
            for event in ('cog open blocks 37', 'cog tick 5', 'cog tick 20', 'cog tick 25',
                          'cog tick 30', 'cog tick 35', 'cog tick 45', 'cog tick 105',
                          'cog tick 115', 'cog tick 135', 'cog tick 205'):
                assert 'CREATE_PONDER ' + event in recorded, event
            marker = next(line for line in recorded.splitlines() if 'CREATE_PONDER render vertices ' in line)
            assert int(marker.rsplit(' ', 1)[1]) > 0, marker
            world.call('key', 'space', 'tap')
            world.call('key', 'r', 'tap')
            mp.until('scene replay', lambda: 'CREATE_PONDER replay tick 0' in text())
            world.call('key', 'right', 'tap')
            mp.until('gearshift opens', lambda: 'CREATE_PONDER gearshift open blocks 39' in text())
            world.call('key', 'left', 'tap')
            mp.until('cog relay returns', lambda: text().count('CREATE_PONDER cog open blocks 37') >= 2)
            world.call('key', 'escape', 'tap')
            mp.until('scene closed', lambda: world.call('screen')['screen'] != 'mod')
            assert world.call('inventory')['counts'] == before
            assert 'minecraft:diamond_block' in world.call('block', 5, 170, 20)['state']
    print('Cogwheel hover, scene timeline, model geometry, replay, story navigation, and close passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
