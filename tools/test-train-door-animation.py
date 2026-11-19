#!/usr/bin/env python3
"""Check controlled mounted train door animation and sound against Java's chaser."""
import argparse
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

trip = import_module('test-scheduled-train-doors')
train, conductor = trip.train, trip.conductor
mp = conductor.multiplayer
paired_door = import_module('test-paired-train-door')
ENV = {'HORIZON_NO_AUDIO': '1', 'HORIZON_CREATE_TEST_AUDIO': '1', 'HORIZON_CREATE_ELEVATOR_TRACE': '1'}


def number(reply):
    value = reply.partition('entity data: ')[2]
    if not value:
        raise RuntimeError(reply)
    return float(value.rstrip('fd'))


def cues(actor):
    log = actor.socket.parent / 'ctl.log'
    text = log.read_text() if log.exists() else ''
    return {sound: sum(f'CREATE_ELEVATOR_PLAYBACK minecraft:block.iron_door.{sound},4,' in line
                       and line.endswith(',0.125,1') for line in text.splitlines())
            for sound in ('open', 'close')}


def click_pair(world, actor, name, leaf=2, side=-1):
    x, y, z = paired_door.proxy_pos(world, leaf, side)
    world.command(f'/tp {name} {x} {y} {z + side * 2.1} 0 20')
    actor.call('wait', 5)
    actor.call('look-at', x, y + .5, z)
    tick = world.clock()
    actor.call('mouse', 'right', 'click')
    actor.call('wait', 4)
    if world.clock() != tick:
        raise AssertionError('Manual door click advanced the world tick.')


def panel_paths(world, entity, panels, *, side=-1):
    progress = []
    displays = []
    for x, y in panels:
        pos = f'[I;{x},{y},{side}]'
        path = f'CreateTrain.Blocks[{{Pos:{pos}}}].CreateElevatorDoorProgress'
        progress.append(f'/data get entity {entity} {path}')
        proxy = f'@e[type=minecraft:interaction,nbt={{CreateTrainDoorPos:{pos}}},limit=1]'
        part = int(number(world.command(f'/data get entity {proxy} CreatePartIndex'))) - 1
        displays.append(f'@e[type=minecraft:block_display,nbt={{CreatePartIndex:{part}}},limit=1]')
    return progress, displays


def panel_queries(world, entity, panels, *, side=-1):
    progress, displays = panel_paths(world, entity, panels, side=side)
    translations = [f'/data get entity {display} transformation.translation[{axis}]'
                    for display in displays for axis in range(3)]
    return progress, translations


def exercise_moving_pair(world, listeners, actor_name, *, south, right):
    actor = listeners[-1]
    side = 1 if south else -1
    leaf = paired_door.selected_leaf_x(south=south, right=right)
    schedule = paired_door.schedule
    train.setup(world, before_glue=lambda host: paired_door.place_pair(host, south=south),
                take_controls=False, after_station=schedule.place_cargo_stations)
    if len(listeners) > 1:
        world.command(f'/gamemode survival {actor_name}')
        schedule.give_fixture_schedule(world, actor, actor_name, schedule.ITEM_CARGO_PROGRAM)
    else:
        conductor.set_held(world, actor, actor_name, conductor.SCHEDULE,
                           components=schedule.ITEM_CARGO_PROGRAM)
    conductor.click(world, actor, actor_name, 0, from_north=south)
    if conductor.assigned(world) is None:
        raise AssertionError('Conductor did not accept the schedule.')
    origin = paired_door.proxy_pos(world, leaf, side)[0]
    for _ in range(80):
        world.step_to(world.clock() + 1)
        fast_enough = abs(paired_door.train_speed(world)) >= .18
        if fast_enough and abs(paired_door.proxy_pos(world, leaf, side)[0] - origin) > 1.5:
            break
    else:
        raise AssertionError('Train did not reach moving speed.')
    world.commands((f'/attribute {actor_name} minecraft:gravity base set 0',
                    f'/item replace entity {actor_name} hotbar.0 with minecraft:air'))
    actor.call('key', '1', 'tap')

    with (ROOT / 'fixtures/train_door_animation-java.csv').open() as f:
        reference = list(csv.DictReader(f))
    panels = [(2, 2, -1), (2, 3, -1), (3, 2, 1), (3, 3, 1)]
    queries, displays = panel_queries(world, train.ENTITY, [(x, y) for x, y, _ in panels], side=side)
    if any(number(reply) != 0 for reply in world.commands(queries)):
        raise AssertionError('Doors began mid-animation.')
    for listener in listeners:
        listener.call('wait', 3)
    baseline = [cues(listener) for listener in listeners]
    close_count = 0
    for phase in (reference[9:], reference[:9]):
        click_pair(world, actor, actor_name, leaf, side)
        for row in phase:
            world.step_to(world.clock() + 1)
            if abs(paired_door.train_speed(world)) < .18:
                raise AssertionError(f"Train slowed during animation step {row['step']}.")
            values = [number(reply) for reply in world.commands(queries)]
            expected = float(row['progress'])
            if any(not isclose(value, expected, abs_tol=2e-6) for value in values):
                raise AssertionError(f"Step {row['step']}: progress {values}, Java {expected}.")
            offsets = [number(reply) for reply in world.commands(displays)]
            for index, (x, y, sign) in enumerate(panels):
                start = 3 * index
                actual = offsets[start:start + 3]
                wanted = (sign * float(row['slide']), 0.0, side * float(row['normal']))
                if any(not isclose(a, b, abs_tol=2e-6) for a, b in zip(actual, wanted, strict=True)):
                    raise AssertionError(f"Step {row['step']}: panel {(x, y)} offset {actual}, Java {wanted}.")
            if row['close_cue'] == 'true':
                close_count += 2
            for listener, initial in zip(listeners, baseline, strict=True):
                listener.call('wait', 2)
                expected_cues = {'open': initial['open'], 'close': initial['close'] + close_count}
                if (actual := cues(listener)) != expected_cues:
                    raise AssertionError(f"Step {row['step']}: door cues {actual}, expected {expected_cues}.")
    print(f'Moving paired Train Doors matched {len(reference)} Java chaser and panel offset samples, plus close cues.')


def exercise(world, listeners, *, paired, manual, actor_name):
    build = paired_door.place_pair if paired else trip.place_doors
    train.setup(world, before_glue=build, take_controls=False)
    # Let both origin doors finish opening before the controlled transitions.
    for _ in range(12):
        world.step_to(world.clock() + 1)
    station = ' '.join(map(str, train.STATION))
    if manual:
        world.commands((f'/attribute {actor_name} minecraft:gravity base set 0',
                        f'/item replace entity {actor_name} hotbar.0 with minecraft:air'))
        listeners[-1].call('key', '1', 'tap')
    leaves = [(3, -1, -1), (3, 1, 1)]
    if paired:
        leaves = [(2, -1, -1), (3, -1, 1), (3, 1, 1)]
    panels = [(x, y, z, slide) for x, z, slide in leaves for y in ((2, 3) if paired else (2,))]
    paths = [f'CreateTrain.Blocks[{{Pos:[I;{x},{y},{z}]}}].CreateElevatorDoorProgress'
             for x, y, z, _ in panels]
    with (ROOT / 'fixtures/train_door_animation-java.csv').open() as f:
        reference = list(csv.DictReader(f))
    for actor in listeners:
        actor.call('wait', 3)
    initial = [cues(actor) for actor in listeners]
    opening_leaves = 0 if manual else len(leaves)
    closing_leaves = 2 if manual else len(leaves)
    for row in reference:
        index = int(row['step'])
        if index in (0, 9):
            if manual:
                click_pair(world, listeners[-1], actor_name)
            else:
                mode = 'NONE' if index == 0 else 'ALL'
                world.command(f'/data merge block {station} {{DoorControl:"{mode}"}}')
        world.step_to(world.clock() + 1)
        values = [number(v) for v in world.commands(f'/data get entity {train.ENTITY} {path}' for path in paths)]
        for actor, start_cues in zip(listeners, initial):
            actor.call('wait', 2)
            actual = cues(actor)
            expected_cues = {'open': start_cues['open'] + (opening_leaves if index >= 9 else 0),
                             'close': start_cues['close'] + (closing_leaves if index >= 7 else 0)}
            if actual != expected_cues:
                raise RuntimeError(f'step {index}: door cues {actual}, expected {expected_cues}')
        for value, (x_cell, y_cell, z, slide_sign) in zip(values, panels, strict=True):
            if manual and z > 0:
                expected, slide, displacement = 1.0, 13 / 16, 1 / 32
            else:
                expected, slide, displacement = (float(row[key]) for key in ('progress', 'slide', 'normal'))
            if not isclose(value, expected, abs_tol=2e-6):
                raise RuntimeError(f'step {index}: panel {(x_cell, y_cell, z)} progress {value} vs Java {expected}')
            selector = (f'@e[type=minecraft:block_display,x={train.X+x_cell+1},y={train.Y+y_cell+1},'
                        f'z={train.Z+z},distance=..0.2,limit=1,sort=nearest]')
            x, normal = [number(v) for v in world.commands((
                f'/data get entity {selector} transformation.translation[0]',
                f'/data get entity {selector} transformation.translation[2]'))]
            wanted = (slide_sign * slide, z * displacement)
            if not isclose(x, wanted[0], abs_tol=2e-6) or not isclose(normal, wanted[1], abs_tol=2e-6):
                raise RuntimeError(f'step {index}: panel {(x_cell, y_cell, z)} offset {(x, normal)} vs Java {wanted}')
    print(f'Mounted door progress and display offsets matched all {len(reference)} Java chaser samples.')


def run(args):
    scenario = 'paired-door-animation' if args.paired else 'train-door-animation'
    if args.moving:
        scenario += '-moving'
    if args.south:
        scenario += '-south'
    if args.right:
        scenario += '-right'

    def replay(world, listeners, name):
        if args.moving:
            exercise_moving_pair(world, listeners, name, south=args.south, right=args.right)
        else:
            exercise(world, listeners, paired=args.paired, manual=args.manual, actor_name=name)

    if args.manual:
        scenario += '-manual'
    if args.multiplayer:
        scenario += '-lan'
    with fixture_world(args, scenario,
                       train.STRUCTURE, render=True, pack=args.pack, env=ENV) as world:
        if args.multiplayer:
            port = world.call('lan', 'open', 0, 'commands', 'force')['port']
            with TemporaryDirectory(prefix='hc-train-door-animation-') as scratch, mp.joined_client(
                args, Path(scratch), f'127.0.0.1:{port}', 'DoorViewer', render=True,
                scenario=scenario, pack=args.pack, env=ENV) as guest:
                mp.until('door viewer to join', lambda: any(g['name'] == 'DoorViewer' and g['placed']
                                                           for g in world.call('lan', 'status')['guests']))
                world.command(f'/tp DoorViewer {train.X + 4.5} {train.Y + 3} {train.Z + 4.5}')
                replay(world, [world, guest], 'DoorViewer')
                guest.call('wait', 5)
        else:
            replay(world, [world], '@s')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path)
    parser.add_argument('--multiplayer', action='store_true')
    parser.add_argument('--paired', action='store_true')
    parser.add_argument('--manual', action='store_true')
    parser.add_argument('--moving', action='store_true')
    parser.add_argument('--south', action='store_true')
    parser.add_argument('--right', action='store_true')
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    args = parser.parse_args()
    if args.manual and not args.paired:
        parser.error('--manual requires --paired')
    if args.moving and (not args.paired or not args.manual):
        parser.error('--moving requires --paired and --manual')
    if (args.south or args.right) and not args.moving:
        parser.error('--south and --right use the moving pair fixture')
    run(args)
