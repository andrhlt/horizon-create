#!/usr/bin/env python3
"""Compare split berry count, launch cone and item use with pinned Java."""
import argparse
import csv
import math
import os
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

carrot = import_module('test-potato-cannon-carrot')
multiplayer = import_module('test-multiplayer')
ITEMS = {'sweet': 'minecraft:sweet_berries', 'glow': 'minecraft:glow_berries',
         'chocolate': 'create:chocolate_glazed_berries'}
ORIGIN = (8.5, 101.0, 3.5)


def run(args):
    with (ROOT / 'fixtures/potato-cannon-berries-launch-java.csv').open() as source:
        expected = {row['case']: row for row in csv.DictReader(source)}
    for case in args.case or ITEMS:
        with TemporaryDirectory(prefix='hc-berries-') as scratch:
            with fixture_world(args, 'BerryCannon', render=False, pack=args.pack) as host:
                host.commands(('/fill 5 100 0 12 100 16 minecraft:stone',
                               '/fill 5 101 0 12 106 16 minecraft:air'))
                with carrot.actor_for(host, args, Path(scratch)) as (actor, name):
                    ammo = ITEMS[case]
                    host.commands((f'/gamemode survival {name}', f'/tp {name} 8.5 101 3.5 0 0',
                                   f'/item replace entity {name} hotbar.0 with create:potato_cannon',
                                   f'/item replace entity {name} hotbar.1 with {ammo} 3'))
                    multiplayer.until('ammo', lambda: actor.call('inventory')['counts'].get(ammo) == 3)
                    actor.call('select', 'create:potato_cannon')
                    actor.call('use-item')
                    multiplayer.until('shot', lambda: actor.call('inventory')['counts'].get(ammo) == 2)
                    assert (actor.call('inventory')['held'] or {}).get('damage', 0) == int(expected[case]['damage'])
                    count = int(expected[case]['count'])
                    check = host.command('/execute if entity @e[type=create:potato_projectile]')
                    assert f'Count: {count}' in check, (case, check)
                    center_x = 0.05 / math.sqrt(1 + 0.05 ** 2) * (2 * 1.05)
                    center_z = 1 / math.sqrt(1 + 0.05 ** 2) * (2 * 1.05)
                    vectors = []
                    for i in range(count):
                        host.command(f'/tag @e[type=create:potato_projectile,tag=!berry_sample,limit=1] add berry_{i}')
                        shot = carrot.data(host, f'@e[type=create:potato_projectile,tag=berry_{i},limit=1]')
                        assert shot and ammo in shot, (case, i, shot)
                        pos = tuple(a - b for a, b in zip(carrot.vector(shot, 'Pos'), ORIGIN, strict=True))
                        carrot.near(pos, (-.75, 1.469999999, 1.5), f'{case} barrel')
                        v = carrot.vector(shot, 'Motion')
                        deviation = math.sqrt((v[0] - center_x)**2 + v[1]**2 + (v[2] - center_z)**2)
                        assert math.isclose(deviation, 0.1, abs_tol=2e-5), (case, i, v, deviation)
                        vectors.append(v)
                        host.command(f'/tag @e[type=create:potato_projectile,tag=berry_{i},limit=1] add berry_sample')
                    assert len(set(vectors)) == count, (case, vectors)
                    print(f'{case}: {count} distinct shots, Java launch cone, one ammo and one wear.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--lan', action='store_true')
    parser.add_argument('--case', action='append', choices=tuple(ITEMS))
    os.environ['HORIZON_NO_AUDIO'] = '1'
    run(parser.parse_args())
