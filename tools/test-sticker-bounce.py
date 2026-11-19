#!/usr/bin/env python3
"""Compare pig landings on three Sticker states and stone to pinned Java ticks."""
import argparse
from math import isclose
from pathlib import Path
import re
from fixture_world import fixture_world

NUMBER = re.compile(r'(-?\d+(?:\.\d+)?)d')
# Captured by java-sticker-bounce.patch, positions relative to block base.
JAVA = {
    'sticker': [(1.4, -0.666400013), (1.0, 0.574672024), (1.574672024, 0.484778593),
                (2.059450617, 0.396683029), (2.456133645, 0.310349374)],
    'stone': [(1.4, -0.666400013)] + [(1.0, -0.078400002)] * 4,
    'north': [(1.4, -0.666400013)] + [(1.0, -0.078400002)] * 4,
    'extended': [(1.4, -0.666400013), (1.0, 0.574672024), (1.574672024, 0.484778593),
                 (2.059450617, 0.396683029), (2.456133645, 0.310349374)],
}

def vector(message):
    return tuple(float(x) for x in NUMBER.findall(message))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('ctl', 'client', 'resources'):
        parser.add_argument(field, type=Path)
    parser.add_argument('--pack', type=Path)
    args = parser.parse_args()
    with fixture_world(args, 'StickerBounce', pack=args.pack) as host:
        host.commands((
            '/setblock 10 171 20 create:sticker[facing=up]',
            '/setblock 13 171 20 minecraft:stone',
            '/setblock 16 171 20 create:sticker[facing=north]',
            '/setblock 19 171 20 create:sticker[facing=up,extended=true]', 
            '/summon minecraft:pig 10.5 173 20.5 {Motion:[0.0d,-0.6d,0.0d],Tags:["sticker"]}',
            '/summon minecraft:pig 13.5 173 20.5 {Motion:[0.0d,-0.6d,0.0d],Tags:["stone"]}',
            '/summon minecraft:pig 16.5 173 20.5 {Motion:[0.0d,-0.6d,0.0d],Tags:["north"]}',
            '/summon minecraft:pig 19.5 173 20.5 {Motion:[0.0d,-0.6d,0.0d],Tags:["extended"]}',
        ))
        state = host.call('block', 10, 171, 20)['state']
        assert state.startswith('create:sticker[') and 'facing=up' in state and 'extended=false' in state, state
        for x, facing, extended in ((16, 'north', 'false'), (19, 'up', 'true')):
            state = host.call('block', x, 171, 20)['state']
            assert state.startswith('create:sticker[') and f'facing={facing}' in state and f'extended={extended}' in state, state
        tick = host.clock()
        observed = {name: [] for name in JAVA}
        for index in range(5):
            host.step_to(tick + index + 1)
            for name, expected in JAVA.items():
                selector = f'@e[tag={name},limit=1]'
                position = vector(host.command(f'/data get entity {selector} Pos'))
                velocity = vector(host.command(f'/data get entity {selector} Motion'))
                observed[name].append((position[1] - 171, velocity[1]))
        for name in ('stone', 'sticker', 'north', 'extended'):
            for index, (actual, expected) in enumerate(zip(observed[name], JAVA[name]), 1):
                assert all(isclose(a, b, abs_tol=1e-7) for a, b in zip(actual, expected)), (name, index, actual, expected)
    print('Upright, extended and north Sticker and stone trajectories matched Java.')

if __name__ == '__main__':
    main()
