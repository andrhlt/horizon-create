#!/usr/bin/env python3
"""Click a mounted trapdoor on a real scheduled train between stations."""
import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from fixture_world import fixture_world

mounted = import_module('test-mounted-trapdoors')
schedule = import_module('test-scheduled-station-approach')
train, conductor = schedule.train, schedule.conductor
mp = conductor.multiplayer


def cells(world):
    mounted.mounted_cells(world)
    world.command(f'/data merge block {train.X + 3} {train.Y + 3} {train.Z} '
                  '{Items:[{Slot:0b,id:"minecraft:paper",count:64},{Slot:1b,id:"minecraft:paper",count:7}]}')


def proxy_pos(world):
    selector = '@e[type=minecraft:interaction,nbt={CreateTrainTrapdoorPos:[I;2,2,-1]},limit=1]'
    reply = world.command(f'/data get entity {selector} Pos')
    values = re.findall(r'([-+0-9.eE]+)d', reply)
    if len(values) != 3:
        raise RuntimeError(f'Missing moving trapdoor proxy position: {reply}')
    return tuple(map(float, values))


def speed(world):
    reply = world.command(f'/data get entity {train.ENTITY} CreateTrain.Speed')
    return float(reply.partition('entity data: ')[2].rstrip('d'))


def run(args):
    scenario = 'moving-train-trapdoor-lan' if args.multiplayer else 'moving-train-trapdoor'
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, scenario, train.STRUCTURE, render=True,
                                    pack=args.pack, env=mounted.ENV))
        train.setup(world, after_station=schedule.place_cargo_stations, before_glue=cells, take_controls=False)
        actor, who = world, '@s'
        if args.multiplayer:
            who = 'MovingDoorGuest'
            port = world.call('lan', 'open', 0, 'commands', 'force')['port']
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix='hc-moving-trapdoor-')))
            actor = stack.enter_context(mp.joined_client(args, scratch, f'127.0.0.1:{port}', who,
                                        render=True, scenario=scenario, pack=args.pack, env=mounted.ENV))
            mp.until('guest to join', lambda: any(g['name'] == who and g['placed']
                                                  for g in world.call('lan', 'status')['guests']))
            world.command(f'/gamemode survival {who}')
            schedule.give_fixture_schedule(world, actor, who, schedule.ITEM_CARGO_PROGRAM)
        else:
            conductor.set_held(world, actor, who, conductor.SCHEDULE, components=schedule.ITEM_CARGO_PROGRAM)
        world.command(f'/attribute {who} minecraft:gravity base set 0')
        conductor.click(world, actor, who, 0)
        if conductor.assigned(world) is None:
            raise RuntimeError('Conductor did not accept the schedule')
        world.command(f'/item replace entity {who} hotbar.0 with minecraft:air')
        actor.call('key', '1', 'tap')
        start_x = proxy_pos(world)[0]
        for _ in range(80):
            world.step_to(world.clock() + 1)
            if abs(speed(world)) >= .18 and abs(proxy_pos(world)[0] - start_x) > 1.5:
                break
        else:
            raise RuntimeError('Scheduled train did not reach moving speed')
        v = speed(world)
        x, y, z = proxy_pos(world)
        world.command(f'/tp {who} {x} {y} {z - 1.8} 0 20')
        actor.call('wait', 6)
        before = mounted.heard(actor)
        mounted.mouse_at(actor, (x, y + .09, z))
        path = 'CreateTrain.Blocks[{Pos:[I;2,2,-1]}].BlockState.Properties'
        actual = world.command(f'/data get entity {train.ENTITY} {path}')
        if not all(field in actual for field in ('open: "true"', 'facing: "north"', 'half: "bottom"')):
            raise AssertionError(f'Moving trapdoor click did not match Java open state: {actual}')
        if abs(speed(world) - v) > 1e-9:
            raise AssertionError('The click unexpectedly advanced the train')
        actor.call('wait', 5)
        if mounted.heard(actor)[len(before):] != ['open']:
            raise AssertionError(f'Moving trapdoor cue did not match Java: {mounted.heard(actor)}')
        for _ in range(4):
            world.step_to(world.clock() + 1)
        next_pos = proxy_pos(world)
        if abs(next_pos[0] - x) < .01:
            raise AssertionError(f'Open trapdoor proxy did not move with the train: {x}, {next_pos}')
        print(f'Clicked the moving train trapdoor at speed {v:.5f}; state and muted cue matched Java.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    parser.add_argument('--multiplayer', action='store_true')
    run(parser.parse_args())
