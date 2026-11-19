#!/usr/bin/env python3
"""Compare an attached pie after a real world reopen with Java entity reload.

Java's fixture round-trips the projectile entity NBT in the same world. Horizon
stops and reopens the world; the LAN variant fires as a guest before reconnect.
"""
import argparse
import csv
import math
import os
import re
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world, last_command_message, run_command_harness

carrot = import_module('test-potato-cannon-carrot')
multiplayer = import_module('test-multiplayer')
SHOT = '@e[type=create:potato_projectile,limit=1]'
TARGET = '@e[tag=pie_target,limit=1]'


def sample(host, tick, rows):
    pig = carrot.data(host, TARGET)
    shot = carrot.data(host, SHOT)
    assert pig and shot, (tick, pig, shot)
    health = re.search(r'\bHealth:\s*([\d.]+)f', pig)
    assert health and math.isclose(float(health[1]), 3.0, abs_tol=1e-6), (tick, pig)
    relative = tuple(a - b for a, b in zip(carrot.vector(shot, 'Pos'),
                                             carrot.vector(pig, 'Pos'), strict=True))
    actual = (*relative, *carrot.vector(shot, 'Motion'))
    expected = tuple(float(rows[tick][key]) for key in ('x', 'y', 'z', 'vx', 'vy', 'vz'))
    print(f'tick {tick}: {actual}', flush=True)
    carrot.near(actual, expected, f'tick {tick}')


def run(args):
    with (ROOT / 'fixtures/potato-cannon-pie-reload-stuck-java.csv').open() as source:
        rows = {int(row['tick']): row for row in csv.DictReader(source)}
    with TemporaryDirectory(prefix='hc-pie-reopen-') as scratch:
        with fixture_world(args, 'PieReopen', render=False, pack=args.pack) as host:
            host.commands((
                '/fill 5 100 0 12 100 16 minecraft:stone',
                '/fill 5 101 0 12 106 16 minecraft:air',
                '/fill 7 90 7 7 100 7 minecraft:air',
            ))
            with carrot.actor_for(host, args, Path(scratch)) as (actor, name):
                host.commands((
                    f'/gamemode survival {name}', f'/tp {name} 8.5 101 3.5 0 0',
                    f'/item replace entity {name} hotbar.0 with create:potato_cannon',
                    f'/item replace entity {name} hotbar.1 with minecraft:pumpkin_pie 3',
                    '/summon minecraft:pig 8.0 102.0 8.5 '
                    '{NoAI:1b,NoGravity:1b,PersistenceRequired:1b,Tags:["pie_target"]}',
                ))
                multiplayer.until('cannon and ammo', lambda:
                    actor.call('inventory')['counts'].get('minecraft:pumpkin_pie') == 3)
                actor.call('select', 'create:potato_cannon')
                actor.call('use-item')
                multiplayer.until('fired', lambda:
                    actor.call('inventory')['counts'].get('minecraft:pumpkin_pie') == 2)
                assert (actor.call('inventory')['held'] or {}).get('damage', 0) == 1
                start = host.clock()
                for tick in range(1, 4):
                    host.step_to(start + tick)
                sample(host, 3, rows)
            saved_tick = host.clock()
            game = host.socket.parent / 'game'
            host.stop()
            queries = (
                '/time query gametime', f'/data get entity {TARGET} Health',
                f'/data get entity {TARGET} Pos', f'/data get entity {SHOT} Pos',
                f'/data get entity {SHOT} Motion',
            )
            operations = [{'op': 'cmd', 'cmd': query} for query in queries]
            for _ in range(5):
                operations.append({'op': 'tick', 'n': 1})
                operations.extend({'op': 'cmd', 'cmd': query} for query in queries)
            records = run_command_harness(args, game, 'PieReopen', operations, host.env)
            messages = [last_command_message(record) for record in records]
            assert len(messages) == 30, len(messages)
            for offset in range(6):
                tick = 3 + offset
                clock, health, pig, shot, motion = messages[offset * 5:offset * 5 + 5]
                actual_clock = int(clock.split()[-2])
                assert actual_clock == saved_tick + offset, (tick, actual_clock, saved_tick)
                assert health.endswith('3.0f'), (tick, health)
                def vec(message):
                    value = re.search(r'entity data: \[([^\]]+)\]', message)
                    assert value, message
                    return tuple(float(part.strip().removesuffix('d')) for part in value[1].split(','))
                relative = tuple(a - b for a, b in zip(vec(shot), vec(pig), strict=True))
                actual = (*relative, *vec(motion))
                expected = tuple(float(rows[tick][key]) for key in ('x', 'y', 'z', 'vx', 'vy', 'vz'))
                print(f'cold tick {tick}: {actual}', flush=True)
                carrot.near(actual, expected, f'cold tick {tick}')
    print('World reopen matched Java entity reload for the attached pie.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--lan', action='store_true')
    os.environ['HORIZON_NO_AUDIO'] = '1'
    run(parser.parse_args())
