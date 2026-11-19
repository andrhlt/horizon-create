#!/usr/bin/env python3
"""Compare an empty-stew projectile hitting a stone wall with pinned Java."""
import argparse
import csv
import os
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

carrot = import_module('test-potato-cannon-carrot')
multiplayer = import_module('test-multiplayer')
SHOT = '@e[type=create:potato_projectile,limit=1]'
BOWL = '@e[type=minecraft:item,nbt={Item:{id:"minecraft:bowl"}},limit=1]'
ORIGIN = (8, 101, 3)


def run(args):
    with (ROOT / 'fixtures/potato-cannon-stew-block-launch-java.csv').open() as source:
        launch = next(csv.DictReader(source))
    with (ROOT / 'fixtures/potato-cannon-stew-block-states-java.csv').open() as source:
        rows = list(csv.DictReader(source))[:3]
    with TemporaryDirectory(prefix='hc-stew-block-') as scratch:
        with fixture_world(args, 'StewBlock', render=False, pack=args.pack) as host:
            host.commands(('/fill 6 99 -2 11 105 7 minecraft:air',
                           '/setblock 8 101 3 minecraft:stone',
                           '/setblock 8 100 2 minecraft:stone',
                           '/setblock 9 99 0 minecraft:stone'))
            with carrot.actor_for(host, args, Path(scratch)) as (actor, name):
                host.commands((f'/gamemode survival {name}', f'/tp {name} 9.25 100 0.0 0 0',
                               f'/item replace entity {name} hotbar.0 with create:potato_cannon',
                               f'/item replace entity {name} hotbar.1 with minecraft:suspicious_stew'))
                multiplayer.until('cannon and stew', lambda:
                    actor.call('inventory')['counts'].get('minecraft:suspicious_stew', 0) == 1)
                actor.call('select', 'create:potato_cannon')
                actor.call('use-item')
                multiplayer.until('stew shot', lambda:
                    actor.call('inventory')['counts'].get('minecraft:suspicious_stew', 0) == 0)
                assert (actor.call('inventory')['held'] or {}).get('damage', 0) == int(launch['damage'])
                shot = carrot.data(host, SHOT)
                assert shot
                position = tuple(a - b for a, b in zip(carrot.vector(shot, 'Pos'), ORIGIN, strict=True))
                actual = (*position, *carrot.vector(shot, 'Motion'))
                expected = tuple(float(launch[key]) for key in ('x', 'y', 'z', 'vx', 'vy', 'vz'))
                carrot.near(actual, expected, 'stew launch')
                start = host.clock()
                for row in rows:
                    host.step_to(start + int(row['tick']))
                    assert host.call('block', 8, 101, 3)['block'] == 'minecraft:stone'
                    assert (carrot.data(host, SHOT) is not None) == (int(row['projectiles']) > 0), row
                    assert (carrot.data(host, BOWL) is not None) == (int(row['bowls']) > 0), row
    print('Empty stew wall hit and bowl drop matched Java.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--lan', action='store_true')
    os.environ['HORIZON_NO_AUDIO'] = '1'
    run(parser.parse_args())
