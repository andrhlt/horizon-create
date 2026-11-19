#!/usr/bin/env python3
"""Compare cannon shots wearing enchanted Copper and Netherite Backtanks."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

save = import_module('test-potato-projectile-save')
multiplayer = save.multiplayer
CANNON = 'create:potato_cannon'
AMMO = 'minecraft:potato'


def tank_state(world, who):
    stack = world.command(f'/data get entity {who} equipment.chest').partition('entity data: ')[2]
    item = re.search(r'\bid:\s*"([^"]+)"', stack)
    charge = re.search(r'"create:banktank_air":\s*(\d+)', stack)
    capacity = re.search(r'"create:capacity":\s*(\d+)', stack)
    if not item or not charge:
        return None
    return item[1], int(charge[1]), int(capacity[1]) if capacity else 0


def replay(world, actor, who, row):
    offhand = row['hand'] == 'OFF_HAND'
    tank, air, capacity = row['tank'], int(row['initial_air']), int(row['capacity'])
    encoded_tank = f'{{id:"{tank}",count:1}}'
    if capacity:
        encoded_tank = (f'{{id:"{tank}",count:1,components:'
                        f'{{"minecraft:enchantments":{{"create:capacity":{capacity}}}}}}}')
    cannon_slot = 'weapon.offhand' if offhand else 'hotbar.0'
    world.commands((f'/clear {who}',
                    f'/tp {who} 8.5 101 3.5 0 0',
                    f'/setblock 9 101 2 {tank}',
                    f'/data merge block 9 101 2 {{Air:{air},CapacityEnchantment:{capacity},TankItem:{encoded_tank}}}'))
    multiplayer.until('shooter at the tank', lambda: tuple(actor.call('state')['player']['position'][:3])
                      == (8.5, 101.0, 3.5))
    actor.call('interact', 9, 101, 2, 'up')
    multiplayer.until('equipped air and enchantment', lambda: tank_state(world, who) == (tank, air, capacity))
    world.commands((f'/tp {who} 8.5 101 3.5 0 0',
                    f'/item replace entity {who} {cannon_slot} with {CANNON}',
                    f'/item replace entity {who} hotbar.1 with {AMMO} 3'))

    def ready():
        inventory = actor.call('inventory')
        cannon = inventory.get('offhand') if offhand else inventory['hotbar'][0]
        return cannon and cannon.get('item') == CANNON and inventory['counts'].get(AMMO) == 3

    multiplayer.until('cannon and potato in inventory', ready)
    start = tank_state(world, who)
    if start != (tank, air, capacity):
        raise AssertionError(f'Equipped tank {start} differs from fixture {(tank, air, capacity)}.')
    actor.call('select', '1')
    actor.call('use-item')
    multiplayer.until('shot consumed one potato', lambda: actor.call('inventory')['counts'].get(AMMO) == int(row['ammo']))
    end = tank_state(world, who)
    inventory = actor.call('inventory')
    cannon = inventory['offhand'] if offhand else inventory['hotbar'][0]
    expected_tank = (tank, int(row['air']), capacity)
    if end != expected_tank or cannon.get('damage', 0) != int(row['damage']):
        raise AssertionError(f"{row}: tank {end}, cannon {cannon}")
    if 'entity data: ' not in world.command(f'/data get entity {save.PROJECTILE}'):
        raise AssertionError('No projectile appeared.')
    world.command(f'/kill {save.PROJECTILE}')
    print(f"{tank}, capacity {capacity}, {row['hand']}: {air}→{end[1]}, wear {row['damage']}", flush=True)


def run(args):
    with (ROOT / 'fixtures/potato-cannon-armor-java.csv').open() as f:
        reference = list(csv.DictReader(f))
    scenario = 'cannon-tank-variants-lan' if args.lan else 'cannon-tank-variants-solo'
    with fixture_world(args, scenario, pack=args.pack, env={'HORIZON_NO_AUDIO': '1'}) as world:
        world.commands(('/fill 5 100 0 12 100 16 minecraft:stone',
                        '/fill 5 101 0 12 106 16 minecraft:air'))
        with save.shooter_for(world, args, scenario) as (actor, who):
            world.command(f'/gamemode survival {who}')
            for index, row in enumerate(reference):
                if index:
                    actor.call('wait', 20)
                replay(world, actor, who, row)
    print(f'All {len(reference)} Backtank air and cannon wear cases matched Java.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    parser.add_argument('--lan', action='store_true')
    run(parser.parse_args())
