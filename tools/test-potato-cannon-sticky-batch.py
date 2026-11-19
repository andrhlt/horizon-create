#!/usr/bin/env python3
"""Compare cake and fish projectile impact and attachment to Java."""
import argparse
import csv
import math
import os
import re
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

carrot = import_module('test-potato-cannon-carrot')
multiplayer = import_module('test-multiplayer')
SHOT = '@e[type=create:potato_projectile,limit=1]'
TARGET = '@e[tag=pie_target,limit=1]'


def run(args):
    with (ROOT / 'fixtures/potato-cannon-sticky-batch-launch-java.csv').open() as source:
        launch = {row['case']: row for row in csv.DictReader(source)}
    prefix = 'potato-cannon-sticky-batch-' + ('lifetime-' if args.lifetime else '')
    with (ROOT / f'fixtures/{prefix}target-java.csv').open() as source:
        target = {(row['case'], int(row['tick'])): row for row in csv.DictReader(source)}
    with (ROOT / f'fixtures/{prefix}stuck-java.csv').open() as source:
        stuck = {(row['case'], int(row['tick'])): row for row in csv.DictReader(source)}
    cases = args.case or ('cake', 'cod', 'cooked_cod', 'salmon', 'cooked_salmon', 'tropical_fish')
    for case in cases:
        with TemporaryDirectory(prefix='hc-pie-sticky-') as scratch:
            with fixture_world(args, 'PieSticky', render=False, pack=args.pack) as host:
                host.commands((
                    '/fill 5 100 0 12 100 16 minecraft:stone',
                    '/fill 5 101 0 12 106 16 minecraft:air',
                ))
                with carrot.actor_for(host, args, Path(scratch)) as (actor, name):
                    ammo = 'minecraft:' + case
                    initial = 1 if case == 'cake' else 3
                    invulnerable = 0
                    host.commands((
                        f'/gamemode survival {name}',
                        f'/tp {name} 8.5 101 3.5 0 0',
                        f'/item replace entity {name} hotbar.0 with create:potato_cannon',
                        f'/item replace entity {name} hotbar.1 with {ammo} {initial}',
                        '/summon minecraft:pig 8.0 102.0 8.5 '
                        f'{{NoAI:1b,NoGravity:1b,Invulnerable:{invulnerable}b,Tags:["pie_target"]}}',
                    ))
                    multiplayer.until('cannon and ammo', lambda:
                        actor.call('inventory')['counts'].get(ammo, 0) == initial)
                    actor.call('select', 'create:potato_cannon')
                    actor.call('use-item')
                    if args.baseline:
                        actor.call('wait', 5)
                        assert actor.call('inventory')['counts'].get(ammo, 0) == initial
                        assert carrot.data(host, SHOT) is None
                        print(f'{case}: baseline did not fire.', flush=True)
                        continue
                    multiplayer.until('fired', lambda:
                        actor.call('inventory')['counts'].get(ammo, 0) == int(launch[case]['ammo']))
                    held = actor.call('inventory')['held']
                    assert held.get('damage', 0) == int(launch[case]['damage'])
                    start = host.clock()
                    for tick in range(21 if args.lifetime else 5):
                        if tick:
                            host.step_to(start + tick)
                        pig = carrot.data(host, TARGET)
                        shot = carrot.data(host, SHOT)
                        row = target[(case, tick)]
                        health = float(re.search(r'\bHealth:\s*([\d.]+)f', pig)[1])
                        assert math.isclose(health, float(row['health']), abs_tol=1e-6), (
                            case, tick, health, row)
                        assert bool(shot) == (int(row['shots']) > 0), (case, tick, shot, row)
                        if tick == 2:
                            velocity = carrot.vector(pig, 'Motion')
                            expected_velocity = tuple(float(row[key]) for key in ('vx', 'vy', 'vz'))
                            carrot.near(velocity, expected_velocity, f'{case} impact')
                        if shot:
                            expected = stuck[(case, tick)]
                            relative = tuple(
                                a - b for a, b in zip(carrot.vector(shot, 'Pos'),
                                                      carrot.vector(pig, 'Pos'), strict=True))
                            actual = (*relative, *carrot.vector(shot, 'Motion'))
                            values = tuple(float(expected[key]) for key in
                                           ('x', 'y', 'z', 'vx', 'vy', 'vz'))
                            carrot.near(actual, values, f'{case} tick {tick}')
                print(f'{case}: sticky impact and attachment matched Java.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--lan', action='store_true')
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--lifetime', action='store_true')
    parser.add_argument('--case', action='append', choices=('cake', 'cod', 'cooked_cod', 'salmon', 'cooked_salmon', 'tropical_fish'))
    os.environ['HORIZON_NO_AUDIO'] = '1'
    run(parser.parse_args())
