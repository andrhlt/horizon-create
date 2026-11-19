#!/usr/bin/env python3
"""Use paired mounted Train Doors during the Java quarter-turn trace."""
import argparse
import csv
import re
from contextlib import ExitStack
from importlib import import_module
from math import hypot, isclose
from pathlib import Path

from fixture_world import ROOT, fixture_world, last_command_message, run_command_harness

curve = import_module('test-curved-train')
doors = import_module('test-moving-train-door')
animation = import_module('test-train-door-animation')
paired = import_module('test-paired-train-door')
train = curve.train
ENV = {'HORIZON_NO_AUDIO': '1'}
GUEST = 'CurvedPairGuest'


def place_pair(world, material="train_door"):
    y, z = train.Y + 3, train.Z - 1
    for x, hinge in ((train.X + 3, 'left'), (train.X + 4, 'right')):
        world.commands((
            f'/setblock {x} {y-1} {z} minecraft:oak_planks',
            f'/setblock {x} {y} {z} create:{material}[facing=north,half=lower,hinge={hinge}]',
            f'/setblock {x} {y+1} {z} create:{material}[facing=north,half=upper,hinge={hinge}]',
        ))
    world.command(f'/summon minecraft:marker {train.X + 4} {y-1} {train.Z + .5} '
                  '{CreateSuperGlue:1b,From:[-1d,0d,-1.5d],To:[1d,3d,0.5d]}')


def sample(world, actor, who, row, front, rear, leaf_x):
    dx, dz = rear[0] - front[0], rear[1] - front[1]
    length = hypot(dx, dz)
    if not length or abs(dz / length) < .6:
        raise AssertionError('Train was not rotating through the curve.')
    if row['action'] in ('opened', 'closed'):
        x, y, z = doors.proxy_pos(world, leaf_x)
        world.command(f'/tp {who} {x + 2.1 * dz / length} {y} {z - 2.1 * dx / length}')
        actor.call('wait', 5)
        actor.call('look-at', x, y + .5, z)
        tick = world.clock()
        actor.call('mouse', 'right', 'click')
        actor.call('wait', 4)
        if world.clock() != tick:
            raise AssertionError('World tick advanced during paired door click.')
    actual = read_halves(world)
    if actual != row['halves']:
        raise AssertionError(f"{row['tick']} {row['action']}: paired halves {actual}, Java {row['halves']}")


def read_halves(world):
    paths = [f'CreateTrain.Blocks[{{Pos:[I;{x},{y},-1]}}].BlockState.Properties.open'
             for x in (2, 3) for y in (2, 3)]
    return ''.join('1' if state else '0' for state in paired.read_halves(world, paths))


def cold_snapshot(args, world, scenario, panels, saved_tick, reference, display):
    game = world.socket.parent / 'game'
    queries = ['/time query gametime']
    for x, y in panels:
        path = f'CreateTrain.Blocks[{{Pos:[I;{x},{y},-1]}}]'
        queries.extend(f'/data get entity {train.ENTITY} {path}.{property}'
                       for property in ('BlockState.Properties.open', 'CreateElevatorDoorProgress'))
    queries.extend(display)
    records = run_command_harness(args, game, scenario, (
        {'op': 'cmd', 'cmd': query} for query in queries), world.env)
    messages = [last_command_message(record) for record in records]
    if int(messages[0].split()[-2]) != saved_tick:
        raise AssertionError(f'The cold snapshot advanced from tick {saved_tick}: {messages[0]}.')
    door_data = messages[1:1 + 2 * len(panels)]
    states = ''.join('1' if reply.endswith('"true"') else '0' for reply in door_data[::2])
    if states != reference['halves']:
        raise AssertionError(f'Exact cold snapshot at tick {saved_tick}: door states {states}, Java {reference["halves"]}.')
    progress = [animation.number(reply) for reply in door_data[1::2]]
    expected = [float(reference['left_after' if x == 2 else 'right_after']) for x, _ in panels]
    if progress != expected:
        raise AssertionError(f'Exact cold snapshot at tick {saved_tick}: progress {progress}, Java {expected}.')
    offsets = [animation.number(reply) for reply in messages[1 + len(door_data):]]
    for index, (x, y) in enumerate(panels):
        leaf = 'left' if x == 2 else 'right'
        expected = [float(reference[f'{leaf}_{axis}']) for axis in 'xyz']
        actual = offsets[index * 3:index * 3 + 3]
        if any(not isclose(a, b, abs_tol=2e-4) for a, b in zip(actual, expected, strict=True)):
            raise AssertionError(f'Cold panel {(x, y)} world offset {actual}, Java {expected}.')
    print(f'At the exact saved game tick {saved_tick}, all four states and panel transforms matched Java.')


def check_reopened(world, panels, reference):
    actual = read_halves(world)
    if actual != reference['halves']:
        raise AssertionError(f"Reloaded door states {actual}, Java {reference['halves']}.")
    queries, _ = animation.panel_queries(world, train.ENTITY, panels)
    actual = [animation.number(reply) for reply in world.commands(queries)]
    expected = [float(reference['left_after'] if x == 2 else reference['right_after']) for x, _ in panels]
    if actual != expected:
        raise AssertionError(f'Reloaded panel progress {actual}, Java fresh chaser {expected}.')
    print(f"After reopen from Java tick {reference['tick']}, all four states and settled panel endpoints matched.")


def confirm_animation(world, listeners, panels, queries, baseline, close_count, row):
    tick = int(row['tick'])
    progression, display = queries
    values = [animation.number(reply) for reply in world.commands(progression)]
    offsets = [animation.number(reply) for reply in world.commands(display)]
    for index, (x, y) in enumerate(panels):
        if not isclose(values[index], float(row['progress']), abs_tol=2e-6):
            raise AssertionError(f'Tick {tick} panel {(x, y)} progress {values[index]}, Java {row["progress"]}.')
        leaf = 'left' if x == 2 else 'right'
        expected = tuple(float(row[f'{leaf}_{axis}']) for axis in 'xyz')
        actual = offsets[index * 3:index * 3 + 3]
        if any(not isclose(a, b, abs_tol=2e-5) for a, b in zip(actual, expected, strict=True)):
            raise AssertionError(f'Tick {tick} panel {(x, y)} offset {actual}, Java {expected}.')
    check_animation_cues(tick, listeners, baseline, close_count)


def check_animation_cues(tick, listeners, baseline, close_count):
    for listener, initial in zip(listeners, baseline, strict=True):
        listener.call('wait', 2)
        expected = {'open': initial['open'], 'close': initial['close'] + close_count}
        if (actual := animation.cues(listener)) != expected:
            raise AssertionError(f'Tick {tick}: door cues {actual}, Java {expected}.')


def folding_panel_queries(world, panels):
    progress, displays = animation.panel_paths(world, train.ENTITY, panels)
    fields = ('translation', 'left_rotation', 'right_rotation')
    return [(chaser, *(f'/data get entity {display} transformation.{field}[{i}]'
                       for field, size in zip(fields, (3, 4, 4), strict=True)
                       for i in range(size)))
            for chaser, display in zip(progress, displays, strict=True)]


def confirm_folding_animation(world, tick, queries, rows):
    for commands, row in zip(queries, rows, strict=True):
        progress, x, y, z, lx, ly, lz, lw, rx, ry, rz, rw = map(animation.number, world.commands(commands))
        if any(not isclose(value, 0, abs_tol=2e-6) for value in (lx, lz, rx, rz)):
            raise AssertionError(f'Tick {tick}: unexpected panel pitch/roll: {(lx, lz, rx, rz)}')
        qy, qw = ly * rw + lw * ry, lw * rw - ly * ry
        actual = (progress, x, y, z, 2 * qy * qw, 0.0, 1 - 2 * qy * qy)
        expected = tuple(float(row[field]) for field in ('progress', 'tx', 'ty', 'tz', 'dx', 'dy', 'dz'))
        if any(not isclose(a, b, abs_tol=2e-5) for a, b in zip(actual, expected, strict=True)):
            raise AssertionError(f'Tick {tick}, {row["leaf"]} {row["half"]}: panel {actual}, Java {expected}.')


def run(args):
    fixture = 'curved-paired-right' if args.right else 'curved-paired'
    with (ROOT / 'fixtures' / f'{fixture}-train-door-java.csv').open() as f:
        reference = list(csv.DictReader(f))
    animation_rows = {}
    folding_rows = {}
    if args.animation and args.material:
        reference_path = ROOT / 'fixtures/curved-folding-door-animation-java.csv'
        with reference_path.open() as f:
            for row in csv.DictReader(f):
                tick = int(row['tick'])
                folding_rows.setdefault(tick, []).append(row)
                animation_rows[tick] = row
    elif args.animation:
        with (ROOT / 'fixtures/curved-paired-train-door-animation-java.csv').open() as f:
            animation_rows = {int(row['tick']): row for row in csv.DictReader(f)}
    scenario = fixture + ('-animation' if args.animation else '')
    if args.material:
        scenario += '-' + args.material
    reload_row = None
    if args.reload_at is not None:
        scenario += f'-reload-{args.reload_at}'
        with (ROOT / 'fixtures/moving-paired-door-reload-java.csv').open() as f:
            reload_row = next(row for row in csv.DictReader(f) if int(row['tick']) == args.reload_at)
    scenario += '-lan' if args.multiplayer else '-solo'
    environment = animation.ENV if args.animation else ENV
    last_tick = args.reload_at or max(int(reference[-1]['tick']), max(animation_rows, default=0))
    leaf_x = 3 if args.right else 2
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, scenario, train.STRUCTURE,
                                                 render=True, pack=args.pack, env=environment))
        material = args.material + '_door' if args.material else 'train_door'
        train.setup(world, curve.layout, before_glue=lambda host: place_pair(host, material))
        world.command('/attribute @s minecraft:gravity base set 0')
        actor, who = world, '@s'
        guest_stack = stack.enter_context(ExitStack())
        if args.multiplayer:
            who = GUEST
            actor = paired.open_guest(world, args, guest_stack, scenario, environment, who)
            world.commands((f'/gamemode survival {who}', f'/attribute {who} minecraft:gravity base set 0'))
        world.command(f'/item replace entity {who} hotbar.1 with minecraft:air')
        actor.call('key', '2', 'tap')
        start = world.clock()
        panels = [(x, y) for x in (2, 3) for y in (2, 3)]
        listeners = (world, actor) if args.multiplayer else (world,)
        close_count = 0
        try:
            for tick in range(13, last_tick + 1):
                if tick != 13:
                    before = None
                    if tick > 18:
                        # Java keeps its mock driver by the controls each tick.
                        # The offscreen player can walk while the world is frozen.
                        control = world.command(f'/data get entity {train.ENTITY} Pos')
                        x, y, z = map(float, re.findall(f'({train.NUMBER})d', control))
                        before = f'/tp @s {x} {y + 1} {z + 1.5}'
                    world.step_to(start + tick - 13, before=before)
                if tick == 18:
                    world.call('key', 'w', 'down')
                    world.call('wait', 3)
                if tick < 26:
                    continue
                rows = [row for row in reference if int(row['tick']) == tick]
                if not rows and tick not in animation_rows:
                    continue
                speed, ax, _, az, bx, _, bz, cx, _, cz, dx, _, dz = curve.sample(world)
                front = train.X + (ax + bx) / 2, train.Z + (az + bz) / 2
                rear = train.X + (cx + dx) / 2, train.Z + (cz + dz) / 2
                if tick in animation_rows:
                    animation_row = animation_rows[tick]
                    if abs(speed - float(animation_row['speed'])) > 1e-5:
                        raise AssertionError(f'Tick {tick}: train speed {speed}, Java {animation_row["speed"]}.')
                    if tick == min(animation_rows):
                        queries = (folding_panel_queries(world, panels) if args.material
                                   else animation.panel_queries(world, train.ENTITY, panels))
                        baseline = [animation.cues(listener) for listener in listeners]
                    if animation_row['close_cue'] == 'true':
                        close_count += 2
                    if args.material:
                        confirm_folding_animation(world, tick, queries, folding_rows[tick])
                        check_animation_cues(tick, listeners, baseline, close_count)
                    else:
                        confirm_animation(world, listeners, panels, queries, baseline, close_count, animation_row)
                for row in rows:
                    if abs(speed - float(row['speed'])) > 1e-5:
                        raise AssertionError(f"{tick}: train speed {speed}, Java {row['speed']}")
                    sample(world, actor, who, row, front, rear, leaf_x)
        finally:
            world.call('key', 'w', 'up')
        if reload_row is not None:
            if read_halves(world) != reload_row['halves']:
                raise AssertionError('Door states differed before shutdown.')
            guest_stack.close()
            saved_tick = world.clock()
            if args.cold_snapshot:
                world.stop()
                cold_snapshot(args, world, scenario, panels, saved_tick, reload_row, queries[1])
                world.open()
            else:
                world.restart()
            print(f'World advanced {world.clock() - saved_tick} ticks before the first reopen sample.', flush=True)
            check_reopened(world, panels, reload_row)
            if args.multiplayer:
                paired.open_guest(world, args, guest_stack, scenario, environment, who)
                check_reopened(world, panels, reload_row)
            return
    print(f'Curved paired mounted Train Doors matched all {len(reference)} Java samples.')
    if args.animation:
        print(f'All {len(animation_rows)} Java chaser, world offset, speed and closing-cue samples matched.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    parser.add_argument('--multiplayer', action='store_true')
    parser.add_argument('--right', action='store_true')
    parser.add_argument('--animation', action='store_true')
    parser.add_argument('--material', choices=('andesite', 'copper'))
    parser.add_argument('--reload-at', choices=(77, 79), type=int)
    parser.add_argument('--cold-snapshot', action='store_true')
    args = parser.parse_args()
    if args.material and (args.reload_at or args.right):
        parser.error('--material uses the left-leaf curved replay without reload')
    if args.cold_snapshot and not args.reload_at:
        parser.error('--cold-snapshot requires --reload-at')
    if args.reload_at and (not args.animation or args.right):
        parser.error('--reload-at requires the left-leaf animation fixture')
    run(args)
