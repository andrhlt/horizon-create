#!/usr/bin/env python3
"""Click a mounted Train Door on a scheduled train between stations."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

moving = import_module('test-moving-train-trapdoor')
doors = import_module('test-scheduled-train-doors')
train, conductor, schedule, mp = moving.train, moving.conductor, moving.schedule, moving.mp


def proxy_pos(world, local_x=3, local_z=-1):
    selector = f'@e[type=minecraft:interaction,nbt={{CreateTrainDoorPos:[I;{local_x},2,{local_z}]}},limit=1]'
    reply = world.command(f'/data get entity {selector} Pos')
    values = re.findall(r'([-+0-9.eE]+)d', reply)
    if len(values) != 3:
        raise RuntimeError(f'Missing moving Train Door proxy: {reply}')
    return tuple(map(float, values))


def run(args):
    with (ROOT / 'fixtures/moving-train-door-java.csv').open() as f:
        rows = list(csv.DictReader(f))
    scenario = 'moving-train-door-lan' if args.multiplayer else 'moving-train-door'
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, scenario, train.STRUCTURE, render=True,
                                    pack=args.pack, env={'HORIZON_NO_AUDIO':'1'}))
        train.setup(world, after_station=schedule.place_cargo_stations, before_glue=doors.place_doors, take_controls=False)
        actor, who = world, '@s'
        if args.multiplayer:
            who = 'TrainDoorGuest'
            port = world.call('lan', 'open', 0, 'commands', 'force')['port']
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix='hc-td-')))
            actor = stack.enter_context(mp.joined_client(args, scratch, f'127.0.0.1:{port}', who,
                                        render=True, scenario=scenario, pack=args.pack, env={'HORIZON_NO_AUDIO':'1'}))
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
            if abs(moving.speed(world)) >= .18 and abs(proxy_pos(world)[0] - start_x) > 1.5:
                break
        else:
            raise RuntimeError('Scheduled train did not reach moving speed')
        speed = moving.speed(world)
        paths = [f'CreateTrain.Blocks[{{Pos:[I;3,{h},-1]}}].BlockState.Properties.open' for h in (2,3)]
        for row in rows:
            if row['action'] in ('opened', 'closed'):
                x,y,z = proxy_pos(world)
                world.command(f'/tp {who} {x} {y - .5} {z - 1.8} 0 20')
                actor.call('wait', 6)
                actor.call('look-at', x, y, z)
                actor.call('mouse', 'right', 'click')
                actor.call('wait', 4)
            elif row['action'].endswith('_next_tick'):
                world.step_to(world.clock() + 1)
            actual = [value.endswith('"true"') for value in world.commands(
                f'/data get entity {train.ENTITY} {path}' for path in paths)]
            expected = [row['lower_open'] == 'true', row['upper_open'] == 'true']
            if actual != expected:
                raise AssertionError(f'{row["action"]}: expected {expected}, got {actual}')
            if abs(moving.speed(world)) < .18:
                raise AssertionError('The train stopped during the interaction')
        x = proxy_pos(world)[0]
        for _ in range(4):
            world.step_to(world.clock() + 1)
        if abs(proxy_pos(world)[0] - x) < .01:
            raise AssertionError('Door proxy did not follow the moving train')
        print(f'Moving Train Door clicks at speed {speed:.5f} matched all {len(rows)} Java observations.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    parser.add_argument('--multiplayer', action='store_true')
    run(parser.parse_args())
