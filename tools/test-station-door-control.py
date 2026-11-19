#!/usr/bin/env python3
"""Configure the station door selector and compare the scheduled Java train trace."""
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

def place_doors(world):
    x, y, z = train.X + 4, train.Y + 3, train.Z
    commands = []
    for dz, facing in ((-1, 'north'), (1, 'south')):
        commands.extend((f'/setblock {x} {y-1} {z+dz} minecraft:oak_planks',
                         f'/setblock {x} {y} {z+dz} create:train_door[facing={facing},half=lower]',
                         f'/setblock {x} {y+1} {z+dz} create:train_door[facing={facing},half=upper]'))
    commands.append(f'/summon minecraft:marker {x + 0.5} {y-1} {z + 0.5} {{CreateSuperGlue:1b,From:[-0.5d,0d,-1.5d],To:[0.5d,3d,1.5d]}}')
    world.commands(commands)

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        cli.add_argument(name, type=Path)
    cli.add_argument('--pack', type=Path)
    cli.add_argument('--multiplayer', action='store_true')
    args = cli.parse_args()
    with (ROOT / 'fixtures/scheduled-train-doors-java.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, 'scheduled-train-doors-lan' if args.multiplayer else 'scheduled-train-doors', train.STRUCTURE, render=True, pack=args.pack, env={'HORIZON_NO_AUDIO':'1'}))
        train.setup(world, after_station=schedule.place_cargo_stations, before_glue=place_doors, take_controls=False)
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
        x, y, z = schedule.approach.DESTINATION
        world.command(f'/tp {who} {x + .5} {y} {z + 2.5} 180 20')
        actor.call('wait', 5)
        actor.call('look-at', x + .5, y + .45, z + .5)
        actor.call('mouse', 'right', 'click')
        conductor.multiplayer.until('station door control', lambda: any(
            button['label'] == 'Onboard Door Control' for button in actor.call('screen')['buttons']))
        button = next(button for button in actor.call('screen')['buttons'] if button['label'] == 'Onboard Door Control')
        actor.call('scroll-at', button['x'] + button['w'] / 2, button['y'] + button['h'] / 2, -1)
        actor.call('key', 'esc', 'tap')
        actor.call('wait', 5)
        conductor.multiplayer.until('north door control to reach the host', lambda:
            '"NORTH"' in world.command(f'/data get block {x} {y} {z} DoorControl'))
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
        print(f'Mounted doors matched all {len(rows)} Java samples.')

if __name__ == '__main__':
    main()
