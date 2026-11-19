#!/usr/bin/env python3
"""Use adjacent mounted Train Doors and compare all four halves with Java."""
import argparse
import csv
import re
from contextlib import ExitStack
from tempfile import TemporaryDirectory
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT, fixture_world

doors = import_module('test-scheduled-train-doors')
from_moving_door = import_module('test-moving-train-door')
train, schedule, conductor = from_moving_door.train, from_moving_door.schedule, from_moving_door.conductor
train_speed = from_moving_door.moving.speed
proxy_pos = from_moving_door.proxy_pos


def iron_door_cues(listener):
    log = listener.socket.parent / 'ctl.log'
    return [line.partition('CREATE_ELEVATOR_PLAYBACK ')[2].split(',')
            for line in log.read_text().splitlines()
            if 'CREATE_ELEVATOR_PLAYBACK minecraft:block.iron_door.' in line]


def check_cues(listener, start_count, expected):
    cues = iron_door_cues(listener)[start_count:]
    sounds = [expected['sound']] * int(expected['count'])
    if [cue[0] for cue in cues] != sounds:
        raise AssertionError(f"{expected['action']}: played {cues}, expected {sounds}")
    for cue in cues:
        volume, pitch = map(float, cue[-2:])
        if cue[1] != '4' or abs(volume - .3) > 1e-6 or not .9 <= pitch <= 1.0:
            raise AssertionError(f'Unexpected paired Train Door cue: {cue}')


def selected_leaf_x(*, south, right):
    if south:
        return 2 if right else 3
    return 3 if right else 2


def place_pair(host, *, south=False, same_hinge=False, different_facing=False,
               material="train_door", mate_material=None):
    mate = mate_material or material
    doors.place_doors(host, mate)
    side = 1 if south else -1
    facing = 'south' if south else 'north'
    far_facing = 'south' if different_facing else facing
    near_hinge, far_hinge = ('right', 'left') if south else ('left', 'right')
    if same_hinge:
        far_hinge = near_hinge
    x, y, z = train.X + 3, train.Y + 3, train.Z + side
    host.commands((f'/setblock {x} {y-1} {z} minecraft:oak_planks',
        f'/setblock {x} {y} {z} create:{material}[facing={facing},half=lower,hinge={near_hinge}]',
        f'/setblock {x} {y+1} {z} create:{material}[facing={facing},half=upper,hinge={near_hinge}]',
        f'/setblock {x+1} {y} {z} create:{mate}[facing={far_facing},half=lower,hinge={far_hinge}]',
        f'/setblock {x+1} {y+1} {z} create:{mate}[facing={far_facing},half=upper,hinge={far_hinge}]',
        f'/summon minecraft:marker {x + .5} {y-1} {train.Z + .5} {{CreateSuperGlue:1b,From:[-0.5d,0d,-1.5d],To:[0.5d,3d,1.5d]}}'))


def place_end_pair(world, facing):
    doors.place_doors(world)
    x, y, z = train.X + 4, train.Y + 3, train.Z
    left_z = z - 1 if facing == 'east' else z + 1
    world.commands(
        f'/setblock {x} {y + dy} {at} create:train_door[facing={facing},half={half},hinge={hinge}]'
        for at, hinge in ((left_z, 'left'), (z, 'right'))
        for dy, half in ((0, 'lower'), (1, 'upper'))
    )


def open_guest(world, args, guest_stack, scenario, env, name):
    port = world.call('lan', 'open', 0, 'commands', 'force')['port']
    scratch = Path(guest_stack.enter_context(TemporaryDirectory(prefix='hc-paired-')))
    guest = guest_stack.enter_context(doors.conductor.multiplayer.joined_client(
        args, scratch, f'127.0.0.1:{port}', name, render=True,
        scenario=scenario, pack=args.pack, env=env))
    doors.conductor.multiplayer.until('the door guest to join', lambda: any(
        link['name'] == name and link['placed'] for link in world.call('lan', 'status')['guests']))
    return guest


def material_target(world, leaf, side, material, *, opened):
    # Find the physical target from the carriage pose before consulting any
    # interaction proxy. This also exercises missing proxies.
    reply = world.command(f"/data get entity {train.ENTITY} Pos")
    values = re.findall(r"(" + train.NUMBER + r")d", reply)
    if len(values) != 3:
        raise RuntimeError(f"Missing carriage pose: {reply}")
    x, y, z = map(float, values)
    folding = material in ("andesite", "copper")
    retreat = (0.5 if folding else 0.8125) if opened else 0.0
    depth = 0.21875 if opened and folding else 0.40625
    return x + leaf - retreat, y, z + side + depth


def read_halves(world, paths):
    result = world.commands(f'/data get entity {train.ENTITY} {path}' for path in paths)
    if any('entity data: ' not in value for value in result):
        raise RuntimeError(f'Missing mounted door half: {result}')
    return [value.endswith('"true"') for value in result]


def run(args):
    fixture = 'moving-paired' if args.moving else 'paired'
    if args.south:
        fixture += '-south'
    if args.right:
        fixture += '-right'
    if args.upper:
        fixture += '-upper'
    if args.same_hinge:
        fixture = 'same-hinge'
    if args.different_facing:
        fixture = 'different-facing'
    if args.mixed_state:
        fixture = 'mixed-state-paired'
    door_x = selected_leaf_x(south=args.south, right=args.right)
    side = 1 if args.south else -1
    scenario = fixture
    if args.material:
        scenario += "-" + args.material
    if args.mixed_materials:
        scenario += "-mixed-materials"
    if args.end_facing:
        door_x = 3
        side = -1 if args.end_facing == 'east' else 1
        scenario += '-' + args.end_facing
    clicked_z = 0 if args.end_facing and args.right else side
    if args.reopen:
        scenario += '-reopen'
        with (ROOT / 'fixtures/paired-train-door-save-java.csv').open() as f:
            reopened = {row['action']: [bit == '1' for bit in row['halves']] for row in csv.DictReader(f)}
    scenario += ('-audio' if args.audio else '') + ('-lan' if args.multiplayer else '-solo')
    env = {'HORIZON_NO_AUDIO': '1'}
    if args.audio:
        env.update(HORIZON_CREATE_TEST_AUDIO='1', HORIZON_CREATE_ELEVATOR_TRACE='1')
        with (ROOT / 'fixtures/moving-paired-train-door-audio-java.csv').open() as f:
            expected_cues = {row['action']: row for row in csv.DictReader(f)}
    reference = fixture.removesuffix('-upper') if args.moving else fixture
    if args.south and args.right:
        reference = 'moving-paired-south'
    if args.mixed_materials:
        reference = 'moving-paired-mixed-materials'
    filename = f'{reference}-train-door-java.csv'
    with (ROOT / 'fixtures' / filename).open() as f:
        rows = list(csv.DictReader(f))
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, scenario, train.STRUCTURE, render=True, pack=args.pack,
                       env=env))
        def configure_pair(host):
            if args.end_facing:
                place_end_pair(host, args.end_facing)
            else:
                place_pair(host, south=args.south, same_hinge=args.same_hinge,
                           different_facing=args.different_facing,
                           material=args.material + "_door" if args.material else "train_door",
                           mate_material="copper_door" if args.mixed_materials else None)
        train.setup(world, before_glue=configure_pair, take_controls=False,
                    after_station=schedule.place_cargo_stations if args.moving else None)
        actor, who = world, '@s'
        guest_stack = stack.enter_context(ExitStack())
        if args.multiplayer:
            who = 'ManualDoorGuest'
            actor = open_guest(world, args, guest_stack, scenario, env, who)
        world.command(f'/attribute {who} minecraft:gravity base set 0')
        if args.moving:
            if args.multiplayer:
                world.command(f'/gamemode survival {who}')
                schedule.give_fixture_schedule(world, actor, who, schedule.ITEM_CARGO_PROGRAM)
            else:
                conductor.set_held(world, actor, who, conductor.SCHEDULE, components=schedule.ITEM_CARGO_PROGRAM)
            conductor.click(world, actor, who, 0, from_north=args.south)
            if conductor.assigned(world) is None:
                raise RuntimeError('Conductor did not accept the schedule')
            def target_x():
                if args.material:
                    return material_target(world, door_x, side, args.material, opened=False)[0]
                return proxy_pos(world, door_x, clicked_z)[0]

            start_x = target_x()
            for _ in range(80):
                world.step_to(world.clock() + 1)
                if abs(train_speed(world)) >= .18 and abs(target_x() - start_x) > 1.5:
                    break
            else:
                raise RuntimeError('Scheduled train did not reach moving speed')
        world.command(f'/item replace entity {who} hotbar.0 with minecraft:air')
        actor.call('key', '1', 'tap')
        x, y, z = train.X + 3, train.Y + 3, train.Z + side
        leaf_order = (3, 2) if args.south else (2, 3)
        leaves = [(leaf, side) for leaf in leaf_order]
        if args.end_facing:
            leaves = [(door_x, side), (door_x, 0)]
        paths = [f'CreateTrain.Blocks[{{Pos:[I;{leaf},{h},{z_cell}]}}].BlockState.Properties.open'
                 for leaf, z_cell in leaves for h in (2, 3)]
        if args.mixed_state:
            world.commands(
                f'/data modify entity {train.ENTITY} {path} set value "false"' for path in paths[:2])
            world.step_to(world.clock() + 1)
        listeners = (world, actor) if args.multiplayer else (world,)
        errors = []
        start_tick = world.clock()
        for index, row in enumerate(rows):
            if row['action'] in ('closed', 'opened'):
                if index > 1:
                    world.step_to(world.clock() + 1)
                # Open leaves slide outward; closed leaves return to their
                # original block's north-facing plane.
                if args.end_facing:
                    aim_x, feet_y, aim_z = proxy_pos(world, door_x, clicked_z)
                    aim_y = feet_y + .5 + int(args.upper)
                elif args.moving:
                    if args.material:
                        aim_x, door_y, aim_z = material_target(world, door_x, side, args.material, opened=row["action"] == "closed")
                    else:
                        aim_x, door_y, aim_z = proxy_pos(world, door_x, side)
                    aim_y = door_y + .5 + int(args.upper)
                    feet_y = door_y
                else:
                    center_x = x + 0.5 + int(args.right)
                    if (args.same_hinge or args.different_facing) and row['action'] == 'opened':
                        # The still-open right leaf extends over the left leaf's center.
                        center_x = x + 0.08
                    slide = (0.8 if args.right else -0.8) if row['action'] == 'closed' else 0.0
                    aim_x, aim_y, aim_z = center_x + slide, y + .5 + int(args.upper), z + .9
                    feet_y = y
                if args.end_facing:
                    # The longer west-center approach misses the leaf on a moving train.
                    reach = 1.15 if args.moving and args.end_facing == 'west' and args.right else 2.1
                    position = (aim_x - side * reach, feet_y, aim_z)
                else:
                    position = (aim_x, feet_y, aim_z + side * 2.1)
                world.command(f'/tp {who} {position[0]} {position[1]} {position[2]} 0 20')
                actor.call('wait', 5)
                actor.call('look-at', aim_x, aim_y, aim_z)
                if args.audio:
                    for listener in listeners:
                        listener.call('wait', 3)
                    prior_cues = [len(iron_door_cues(listener)) for listener in listeners]
                input_tick = world.clock()
                actor.call('mouse', 'right', 'click')
                world.call('wait', 4)
                if args.audio:
                    for listener, prior_count in zip(listeners, prior_cues):
                        listener.call('wait', 4)
                        check_cues(listener, prior_count, expected_cues[row['action']])
                if world.clock() != input_tick:
                    raise AssertionError(f"{row['action']}: game advanced during the click")
            elif row['action'].endswith('_next_tick'):
                world.step_to(world.clock() + 1)
            actual = read_halves(world, paths)
            expected = [row[key] == 'true' for key in ('left_lower', 'left_upper', 'right_lower', 'right_upper')]
            if actual != expected:
                errors.append((row['action'], expected, actual))
            if args.reopen and row['action'].endswith('_next_tick'):
                guest_stack.close()
                world.restart()
                if args.multiplayer:
                    actor = open_guest(world, args, guest_stack, scenario, env, who)
                action = row['action'].removesuffix('_next_tick')
                actual = read_halves(world, paths)
                if actual != reopened[action]:
                    errors.append((f'{action} after reopen', reopened[action], actual))
            if args.moving:
                actual_tick = world.clock() - start_tick
                expected_tick = int(row['tick']) - int(rows[0]['tick'])
                actual_speed = abs(train_speed(world))
                expected_speed = float(row['speed'])
                if actual_tick != expected_tick or abs(actual_speed - expected_speed) > 2e-6:
                    raise AssertionError(f"{row['action']}: tick/speed {(actual_tick, actual_speed)}"
                                         f" versus Java {(expected_tick, expected_speed)}")
        if errors:
            raise AssertionError(f'Manual mounted train door: {errors}')
    print('Paired mounted Train Doors and next-tick persistence matched Java.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    parser.add_argument('--right', action='store_true')
    parser.add_argument('--moving', action='store_true')
    parser.add_argument('--multiplayer', action='store_true')
    parser.add_argument('--south', action='store_true')
    parser.add_argument('--upper', action='store_true')
    parser.add_argument('--same-hinge', action='store_true')
    parser.add_argument('--different-facing', action='store_true')
    parser.add_argument('--mixed-state', action='store_true')
    parser.add_argument('--end-facing', choices=('east', 'west'))
    parser.add_argument('--material', choices=('andesite', 'copper', 'brass', 'framed_glass'))
    parser.add_argument('--mixed-materials', action='store_true')
    parser.add_argument('--audio', action='store_true')
    parser.add_argument('--reopen', action='store_true')
    args = parser.parse_args()
    if args.mixed_materials and args.material != 'andesite':
        parser.error('--mixed-materials requires an andesite left leaf and a copper mate')
    if args.material and (not args.moving or args.south or args.right or args.upper or args.end_facing):
        parser.error('--material uses the left lower half of a moving north-facing pair')
    if args.south and not args.moving:
        parser.error('--south requires --moving')
    if args.upper and not args.moving and args.right:
        parser.error('--upper requires a moving pair or the stationary left leaf')
    if args.same_hinge and (args.moving or args.right or args.upper):
        parser.error('--same-hinge requires the stationary left lower half')
    if args.different_facing and (args.moving or args.right or args.upper or args.same_hinge):
        parser.error('--different-facing requires the stationary left lower half')
    if args.reopen and (args.moving or args.right or args.upper or args.same_hinge or args.different_facing):
        parser.error('--reopen requires the stationary left lower half')
    if args.audio and not args.moving:
        parser.error('--audio requires --moving')
    if args.mixed_state and (args.moving or args.right or args.upper or args.same_hinge
                             or args.different_facing or args.reopen):
        parser.error('--mixed-state uses the stationary left lower half')
    if args.end_facing and (args.south or (args.upper and not args.moving) or args.same_hinge
                            or args.different_facing or args.mixed_state or args.reopen):
        parser.error('--end-facing requires a matching east- or west-facing pair')
    run(args)
