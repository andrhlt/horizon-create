#!/usr/bin/env python3
"""Compare Placard placement states with pinned Create Java observations."""
import argparse
import csv
from pathlib import Path
from fixture_world import ROOT, fixture_world
from importlib import import_module

mp = import_module('test-multiplayer')
probe = import_module('test-nozzle')


def run(args):
    with (ROOT / 'fixtures/placard-placement-java.csv').open(newline='') as file:
        rows = list(csv.DictReader(file))
    with fixture_world(args, 'PlacardOrientation', render=True, pack=args.pack, env={'HORIZON_NO_AUDIO': '1'}) as game:
        support = (5, 172, 20)
        game.commands((
            "/fill 1 170 16 9 170 24 minecraft:stone",
            "/setblock 4 173 20 minecraft:stone",
            "/setblock 5 167 20 minecraft:stone",
        ))
        for row in rows:
            side, yaw = row['side'], int(row['yaw'])
            print(f'testing {side} yaw {yaw}', flush=True)
            if side in ('up', 'down'):
                feet = (5.05, 174, 20.5) if side == 'up' else (5.5, 168, 20.5)
                pitch = 90 if side == 'up' else -90
                look_yaw = yaw
            else:
                feet, look_yaw = {'north': ((5.5, 171, 17.5), 0), 'south': ((5.5, 171, 23.5), 180),
                                  'west': ((2.5, 171, 20.5), 270), 'east': ((8.5, 171, 20.5), 90)}[side]
                pitch = 0
            target = probe.add(support, probe.OFFSETS[side])
            # The lower platform supports the underside test; leave a clear
            # vertical ray through the upper platform when looking upward.
            floor = 'air' if side == 'down' else 'stone'
            for command in (f'/setblock 5 170 20 minecraft:{floor}',
                            f'/setblock {probe.xyz(target)} minecraft:air', '/setblock 5 172 20 minecraft:stone',
                            f'/tp @s {probe.xyz(feet)} {look_yaw} {pitch}', '/gamemode survival',
                            '/item replace entity @s hotbar.0 with create:placard'):
                game.call('command', command)
            mp.until('the placard to reach the player', lambda: mp.count(game, 'create:placard') == 1)
            game.call('select', 'create:placard')
            mp.until('support is targeted', lambda: (game.call('looking-at').get('block') or {}).get('pos') == list(support))
            game.call('mouse', 'right', 'click')
            expected = f"face={row['face']},facing={row['facing']}"
            try:
                mp.until(f'{side} yaw {yaw} placement', lambda: expected in probe.state(game, target))
            except RuntimeError as error:
                raise AssertionError((side, yaw, expected, probe.state(game, target))) from error
    print('All 24 Java face and yaw placement observations matched.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
