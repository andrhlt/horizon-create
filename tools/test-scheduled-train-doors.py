#!/usr/bin/env python3
"""Compare mounted train doors with the scheduled Java train trace."""
import argparse
from contextlib import ExitStack
from tempfile import TemporaryDirectory
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
from fixture_world import ROOT, fixture_world

schedule = import_module('test-scheduled-station-approach')
train = schedule.train
conductor = schedule.conductor

def place_doors(world, material="train_door"):
    x, y, z = train.X + 4, train.Y + 3, train.Z
    commands = []
    for dz, facing in ((-1, 'north'), (1, 'south')):
        commands.extend((f'/setblock {x} {y-1} {z+dz} minecraft:oak_planks',
                         f'/setblock {x} {y} {z+dz} create:{material}[facing={facing},half=lower]',
                         f'/setblock {x} {y+1} {z+dz} create:{material}[facing={facing},half=upper]'))
    commands.append(f'/summon minecraft:marker {x + 0.5} {y-1} {z + 0.5} {{CreateSuperGlue:1b,From:[-0.5d,0d,-1.5d],To:[0.5d,3d,1.5d]}}')
    world.commands(commands)

def place_platform_pair(world, x):
    commands = []
    for dz, facing in ((-2, 'north'), (2, 'south')):
        y, z = train.Y + 3, train.Z + dz
        commands.extend((
            f'/setblock {x} {y-1} {z} minecraft:smooth_stone',
            f'/setblock {x} {y} {z} minecraft:iron_door[facing={facing},half=lower]',
            f'/setblock {x} {y+1} {z} minecraft:iron_door[facing={facing},half=upper]',
        ))
    world.commands(commands)


def platform_state(world, x):
    return ''.join(
        '-' if (block := world.call('block', x, train.Y + dy, train.Z + dz))['block'] != 'minecraft:iron_door'
        else '1' if 'open=true' in block['state'] else '0'
        for dz in (-2, 2) for dy in (3, 4)
    )


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        cli.add_argument(name, type=Path)
    cli.add_argument('--pack', type=Path)
    cli.add_argument('--multiplayer', action='store_true')
    platforms_mode = cli.add_mutually_exclusive_group()
    platforms_mode.add_argument('--platform', action='store_true')
    platforms_mode.add_argument('--terminal-platform', action='store_true')
    args = cli.parse_args()
    with (ROOT / 'fixtures/scheduled-train-doors-java.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    if args.platform or args.terminal_platform:
        name = 'train-terminal-platform' if args.terminal_platform else 'train-platform-doors'
        with (ROOT / f'fixtures/{name}-java.csv').open(newline='') as f:
            platforms = {int(row['tick']): row['platform_halves'] for row in csv.DictReader(f)}
        rows = [row for row in rows if int(row['tick']) in platforms]
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, 'scheduled-train-doors-lan' if args.multiplayer else 'scheduled-train-doors', train.STRUCTURE, render=True, pack=args.pack, env={'HORIZON_NO_AUDIO':'1'}))
        def build_doors(host):
            place_doors(host)
            if args.platform:
                place_platform_pair(host, train.X + 4)

        train.setup(world, after_station=schedule.place_cargo_stations, before_glue=build_doors, take_controls=False)
        world.command(f'/data merge block {schedule.coordinates(schedule.approach.DESTINATION)} {{DoorControl:"NORTH"}}')
        paths = [f'CreateTrain.Blocks[{{Pos:[I;3,{y},{z}]}}].BlockState.Properties.open'
                 for z in (-1, 1) for y in (2, 3)]
        for path in paths:
            raw = world.command(f'/data get entity {train.ENTITY} {path}')
            if 'entity data: ' not in raw:
                raise RuntimeError(f'Expected mounted door half: {path}: {raw}')
        actor, who = world, '@s'
        if args.multiplayer:
            who = 'DoorGuest'
            port = world.call('lan', 'open', 0, 'commands', 'force')['port']
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix='hc-door-guest-')))
            actor = stack.enter_context(conductor.multiplayer.joined_client(
                args, scratch, f'127.0.0.1:{port}', who, render=True,
                scenario='scheduled-train-doors', pack=args.pack, env={'HORIZON_NO_AUDIO':'1'}))
            conductor.multiplayer.until('the door guest to join', lambda: any(
                link['name'] == who and link['placed'] for link in world.call('lan', 'status')['guests']))
            world.command(f'/gamemode survival {who}')
        world.command(f'/attribute {who} minecraft:gravity base set 0')
        if args.multiplayer:
            schedule.give_fixture_schedule(world, actor, who, schedule.ITEM_CARGO_PROGRAM)
        else:
            conductor.set_held(world, actor, who, conductor.SCHEDULE, components=schedule.ITEM_CARGO_PROGRAM)
        conductor.click(world, actor, who, 0)
        if conductor.assigned(world) is None:
            raise RuntimeError('The conductor did not accept the schedule')
        start = world.clock()
        differences = []
        for row in rows:
            tick = int(row['tick'])
            world.step_to(start + tick - 22)
            if args.platform or args.terminal_platform:
                if args.terminal_platform and tick == 102:
                    place_platform_pair(world, train.X - 9)
                actual = platform_state(world, train.X + 4) + platform_state(world, train.X - 9)
                if actual != platforms[tick]:
                    differences.append(f'{tick}: platform {actual} vs {platforms[tick]}')
            values = world.commands([*(f'/data get entity {train.ENTITY} {path}' for path in paths),
                f'/data get entity {train.ENTITY} CreateTrain.Speed',
                f'/data get entity {train.ENTITY} CreateTrain.ArrivedStation'])
            bits = ''.join('1' if value.endswith('"true"') else '0' for value in values[:4])
            actual_speed = float(values[4].partition('entity data: ')[2].rstrip('d'))
            is_arrived = 'entity data: ' in values[5] and all(str(v) in values[5] for v in schedule.approach.DESTINATION)
            if bits != row['north_and_south_halves'] or not isclose(actual_speed, float(row['speed']), abs_tol=2e-6) or is_arrived != (row['arrived'] == 'true'):
                differences.append(f'{tick}: {actual_speed:.6f}, {is_arrived}, {bits} vs {row}')
        if differences:
            raise RuntimeError(f'{len(differences)} differences: ' + '; '.join(differences[:12]))
        print(f'Mounted doors matched all {len(rows)} Java samples.' + (' Platform doors matched.' if args.platform or args.terminal_platform else ''))

if __name__ == '__main__':
    main()
