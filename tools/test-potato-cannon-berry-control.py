#!/usr/bin/env python3
"""Compare a controlled ownerless sweet/chocolate berry projectile impact with Java."""
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
SHOT = '@e[type=create:potato_projectile,limit=1]'
TARGET = '@e[tag=glow_control,limit=1]'
ORIGIN = (8.5, 101.0, 3.5)


def run(args):
    with (ROOT / 'fixtures/potato-cannon-berry-control-java.csv').open() as source:
        rows = {(row['case'], int(row['tick'])): row for row in csv.DictReader(source)}
    for case in ('sweet', 'sweet_invulnerable', 'chocolate', 'chocolate_invulnerable'):
        with TemporaryDirectory(prefix='hc-glow-control-') as scratch:
            with fixture_world(args, 'GlowControl', render=False, pack=args.pack) as host:
                host.commands(('/fill 5 100 0 12 100 16 minecraft:stone',
                               '/fill 5 101 0 12 106 16 minecraft:air'))
                with carrot.actor_for(host, args, Path(scratch)):
                    flag = int(case.endswith('_invulnerable'))
                    ammo = 'minecraft:sweet_berries' if case.startswith('sweet') else 'create:chocolate_glazed_berries'
                    host.commands((f'/summon minecraft:pig 8.0 102.0 8.5 {{NoAI:1b,NoGravity:1b,Invulnerable:{flag}b,Tags:["glow_control"]}}',
                                   '/summon create:potato_projectile 8.0 102.47 6.0 '
                                   f'{{Motion:[0.0d,0.0d,2.0d],Item:{{id:"{ammo}",count:1}}}}'))
                    start = host.clock()
                    for tick in range(5):
                        if tick:
                            host.step_to(start + tick)
                        row = rows[(case, tick)]
                        pig = carrot.data(host, TARGET)
                        health = float(re.search(r'\bHealth:\s*([\d.]+)f', pig)[1])
                        effects = re.search(r'\bactive_effects:\s*(\[[^\]]*\])', pig)
                        raw = effects[1] if effects else ''
                        duration = re.search(r'\bduration:\s*(\d+)', raw)
                        amplifier = re.search(r'\bamplifier:\s*(\d+)', raw)
                        status = (int(duration[1]) if duration else -1,
                                  int(amplifier[1]) if amplifier else (0 if duration else -1))
                        if duration:
                            assert 'minecraft:glowing' in raw, (case, tick, raw)
                        actual = (health, *status, int(carrot.data(host, SHOT) is not None))
                        expected = (float(row['health']), int(row['duration']), int(row['amplifier']), int(row['shots']))
                        assert actual == expected, (case, tick, actual, expected)
                        if tick == 1:
                            velocity = carrot.vector(pig, 'Motion')
                            expected_velocity = tuple(float(row[k]) for k in ('vx', 'vy', 'vz'))
                            carrot.near(velocity, expected_velocity, f'{case} impact velocity')
        print(f'{case}: controlled berry hit matched Java ticks 0–4.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--lan', action='store_true')
    os.environ['HORIZON_NO_AUDIO'] = '1'
    run(parser.parse_args())
