#!/usr/bin/env python3
"""Verify Ponder Back returns to the selected creative inventory tab."""
import argparse
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world
from importlib import import_module

mp = import_module('test-multiplayer')


def run(args):
    with TemporaryDirectory(prefix='ponder-creative-') as scratch:
        before, after = (Path(scratch) / name for name in ('before.png', 'after.png'))
        with fixture_world(args, 'PonderCreativeBack', render=True, pack=args.pack,
                           env={'HORIZON_NO_AUDIO': '1', 'CREATE_PONDER_TRACE': '1'}) as world:
            world.command('/item replace entity @s hotbar.0 with create:shaft')
            inventory = world.call('inventory')['counts']
            world.call('key', 'e', 'tap')
            mp.until('creative inventory opens', lambda: world.call('screen')['screen'] == 'creative')
            world.call('click-at', 236, 40)  # Redstone Blocks tab
            world.call('scroll-at', 133, 172, 0)  # Shaft in hotbar
            world.call('wait', 4)
            world.call('screenshot', before)
            world.call('key', 'w', 'down')
            try:
                mp.until('Ponder opens', lambda: world.call('screen')['screen'] == 'mod')
            finally:
                world.call('key', 'w', 'up')
            world.call('key', 'backspace', 'tap')
            mp.until('Back returns to creative', lambda: world.call('screen')['screen'] == 'creative')
            world.call('scroll-at', 133, 172, 0)
            world.call('wait', 4)
            world.call('screenshot', after)
            assert world.call('inventory')['counts'] == inventory
        # The title and item grid are opaque, so the changing world behind the UI
        # cannot affect this comparison. The fixture uses the default GUI size.
        for frame in (before, after):
            subprocess.run(['sips', '--cropToHeightWidth', '570', '900', '--cropOffset',
                            '340', '740', str(frame), '--out', str(frame)],
                           check=True, stdout=subprocess.DEVNULL)
        assert before.read_bytes() == after.read_bytes(), 'Creative tab or contents changed'
    print('Ponder Back preserves the selected creative tab, contents, and inventory.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
