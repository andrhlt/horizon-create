#!/usr/bin/env python3
"""Check a fired Potato Cannon projectile's ammo and owner through world reload."""
import argparse
from contextlib import contextmanager
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module('test-multiplayer')
PROJECTILE = '@e[type=create:potato_projectile,limit=1]'


def read_entity(world, selector, key):
    reply = world.command(f'/data get entity {selector} {key}')
    data = reply.partition('entity data: ')[2]
    if not data:
        raise AssertionError(f'{selector} {key}: missing data ({reply})')
    return data


def stack(world):
    data = read_entity(world, PROJECTILE, 'Item')
    item = re.search(r'\bid:\s*"([^"]+)"', data)
    count = re.search(r'\bcount:\s*(\d+)', data)
    if not item or not count:
        raise AssertionError(f'Could not read projectile item from {data}')
    return item[1], int(count[1])


@contextmanager
def shooter_for(world, args, scenario):
    if not args.lan:
        yield world, '@s'
        return
    guest_name = 'ProjectileOwner'
    port = world.call('lan', 'open', 0, 'commands', 'force')['port']
    with TemporaryDirectory(prefix='hc-proj-save-') as scratch, multiplayer.joined_client(
        args, Path(scratch), f'127.0.0.1:{port}', guest_name,
        render=False, scenario=scenario, pack=args.pack, env={'HORIZON_NO_AUDIO': '1'},
    ) as guest:
        multiplayer.until('guest to join', lambda: any(
            link['name'] == guest_name and link['placed'] for link in world.call('lan', 'status')['guests']))
        yield guest, guest_name


def shoot(world, actor, who, expected):
    world.commands((f'/gamemode survival {who}',
                    f'/tp {who} 8.5 101 3.5 0 -75',
                    f'/item replace entity {who} hotbar.0 with create:potato_cannon',
                    f'/item replace entity {who} hotbar.1 with minecraft:apple {expected[1]}'))
    def ready():
        counts = actor.call('inventory')['counts']
        return counts.get('create:potato_cannon') == 1 and counts.get(expected[0]) == expected[1]

    multiplayer.until('cannon and apple in inventory', ready)
    actor.call('select', 'create:potato_cannon')
    actor.call('use-item')
    multiplayer.until('apple spent', lambda: actor.call('inventory')['counts'].get(expected[0]) == expected[1] - 1)
    item = stack(world)
    if item != expected:
        raise AssertionError(f'Fresh projectile carries {item}, Java {expected}')
    owner = read_entity(world, who, 'UUID')
    actual = read_entity(world, PROJECTILE, 'Owner')
    if actual != owner:
        raise AssertionError(f'Fresh projectile owner {actual} differs from shooter {owner}.')
    return owner, read_entity(world, PROJECTILE, 'UUID')


def run(args):
    with (ROOT / 'fixtures/potato-projectile-save-java.csv').open() as f:
        reference = next(csv.DictReader(f))
    expected = reference['item'], int(reference['count'])
    scenario = 'cannon-projectile-save-lan' if args.lan else 'cannon-projectile-save-solo'
    with fixture_world(args, scenario, pack=args.pack, env={'HORIZON_NO_AUDIO': '1'}) as world:
        world.commands(('/fill 5 100 0 12 100 16 minecraft:stone',
                        '/fill 5 101 0 12 106 16 minecraft:air'))
        with shooter_for(world, args, scenario) as (actor, who):
            owner, projectile_uuid = shoot(world, actor, who, expected)
        world.restart()
        item = stack(world)
        if item != expected:
            raise AssertionError(f'Reopened projectile carries {item}, Java {expected}')
        if read_entity(world, PROJECTILE, 'UUID') != projectile_uuid:
            raise AssertionError('Projectile UUID changed after reopening.')
        actual = read_entity(world, PROJECTILE, 'Owner')
        if actual != owner:
            raise AssertionError(f'Reopened projectile owner {actual} differs from shooter {owner}.')
    print('Apple ammunition, source stack count and shooter identity survived world reopen.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--lan', action='store_true')
    run(parser.parse_args())
