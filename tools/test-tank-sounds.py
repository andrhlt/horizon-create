#!/usr/bin/env python3
"""Compare muted real-player tank exchange sounds with pinned Java events."""
import argparse
from collections import Counter
import csv
from importlib import import_module
from pathlib import Path
import time
from fixture_world import ROOT, fixture_world

mp = import_module('test-multiplayer')


def heard(world):
    return Counter({name: count for name, count in world.call('status')['heard'].items()
                    if name.startswith('minecraft:item.bucket.')})


def run(args):
    with (ROOT / 'fixtures/tank-sounds-java.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    with fixture_world(args, 'TankSounds', render=False, pack=args.pack,
                       env={'HORIZON_NO_AUDIO': '1'}) as world:
        world.call('command', '/gamemode creative')
        world.call('command', '/setblock 9 169 23 minecraft:stone')
        world.call('command', '/tp @s 9.5 170 23.5')
        mp.until('player positioned', lambda: world.call('state')['player']['position'] == [9.5, 170, 23.5])
        for slot, item in enumerate(('water_bucket', 'lava_bucket', 'bucket', 'potion[minecraft:potion_contents={potion:"minecraft:healing"}]', 'glass_bottle')):
            world.call('command', f'/item replace entity @s hotbar.{slot} with minecraft:{item}')
        for creative_tank, mode in ((False, 'CREATIVE'), (True, 'CREATIVE'), (True, 'SURVIVAL')):
            block = 'create:creative_fluid_tank' if creative_tank else 'create:fluid_tank'
            world.call('command', '/gamemode creative')
            world.call('command', '/setblock 9 170 20 minecraft:air')
            world.call('command', f'/setblock 9 170 20 {block}')
            world.call('command', f'/gamemode {mode.lower()}')
            world.call('look-at', 9.5, 170.5, 20.5)
            mp.until('tank targeted', lambda: (world.call('looking-at').get('block') or {}).get('pos') == [9, 170, 20])
            rig = [r for r in rows if r['creative_tank'] == str(creative_tank).lower() and r['mode'] == mode]
            for index, row in enumerate(rig):
                world.call('select', row['item'])
                previous = heard(world)
                world.call('mouse', 'right', 'click')
                expected = Counter([row['sound']]) if row['sound'] else Counter()
                if expected:
                    mp.until('Java tank exchange sound', lambda: sum((heard(world) - previous).values()) >= 1, seconds=5)
                else:
                    # Wait for input processing, including cases that do not mutate the tank.
                    world.call('wait', 3)
                    time.sleep(.15)
                actual = heard(world) - previous
                assert actual == expected, (creative_tank, mode, index, row, actual)
        # An empty bucket used on an ordinary survival tank falls through and
        # cannot exchange fluid; it must not emit an exchange cue.
        world.call('command', '/gamemode creative')
        world.call('command', '/setblock 9 170 20 create:fluid_tank')
        world.call('command', '/gamemode survival')
        world.call('select', 'minecraft:bucket')
        before = heard(world)
        world.call('mouse', 'right', 'click')
        world.call('wait', 3)
        time.sleep(.15)
        assert heard(world) == before, (before, heard(world))
    print('Real-player tank exchange and silent-control sounds matched Java.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
