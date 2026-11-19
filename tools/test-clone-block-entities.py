#!/usr/bin/env python3
"""Guard ordinary block-entity copy/move when changing clone load ordering."""
import argparse
from pathlib import Path
from fixture_world import fixture_world


def run(args):
    with fixture_world(args, 'CloneBlockEntityGuard', render=False,
                       env={'HORIZON_NO_AUDIO': '1'}) as world:
        for name, z in [('chest', 20), ('barrel', 23), ('hopper', 26)]:
            source, copied, moved = f'9 170 {z}', f'15 170 {z}', f'21 170 {z}'
            world.command(f'/setblock {source} minecraft:{name}')
            world.command(f'/item replace block {source} container.0 with minecraft:wheat 17')
            before = world.command(f'/data get block {source} Items').split(': ', 1)[-1]
            assert 'minecraft:wheat' in before and '17' in before, before
            world.command(f'/clone {source} {source} {copied} replace normal')
            assert world.command(f'/data get block {copied} Items').split(': ', 1)[-1] == before
            assert world.command(f'/data get block {source} Items').split(': ', 1)[-1] == before
            world.command(f'/clone {copied} {copied} {moved} replace move')
            assert world.command(f'/data get block {moved} Items').split(': ', 1)[-1] == before
            assert world.call('block', 15, 170, z)['block'] == 'minecraft:air'
    print('Chest, barrel and hopper inventories survived copy and move; copied sources were retained.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument(key, type=lambda p: Path(p).resolve(strict=True))
    run(parser.parse_args())
