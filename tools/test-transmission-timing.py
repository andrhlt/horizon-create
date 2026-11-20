#!/usr/bin/env python3
"""Compare ordinary Clutch and Gearshift redstone timing with the pinned Java fixtures."""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

CHANGE = {5: True, 9: False, 13: True, 17: False}
RIGS = ((8, 102, -12), (8, 102, -8))
LEVER = (8, 103, -10)
BLOCK = (8, 102, -10)
TEST_AUDIO = {'HORIZON_NO_AUDIO': '1', 'HORIZON_CREATE_TEST_AUDIO': '1'}


def java_rows(name):
    with (ROOT / "fixtures" / f"{name}-java.csv").open(newline="") as source:
        reader = csv.reader(source)
        next(reader)
        return list(reader)


def rpm(data):
    match = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)", data)
    return float(match[1]) if match else 0.0


def compare(name, expected, observed):
    differences = [(left, right) for left, right in zip(expected, observed, strict=True) if left != right]
    if differences:
        raise RuntimeError(f"{name} differs in {len(differences)} samples: {differences[:12]}.")
    print(f"{name} matched all {len(expected)} Java state and RPM samples.")


def sample(control, kind, tick, action):
    x, y, z = RIGS[kind]
    block = ('clutch', 'gearshift')[kind]
    powered, gear, shaft = control.commands((
        f'/execute if block {x} {y} {z} create:{block}[axis=x,powered=true]',
        f'/data get block {x} {y} {z}', f'/data get block {x+1} {y} {z}',
    ))
    if powered not in ('Test passed', 'Test failed'):
        raise RuntimeError(f'Unexpected powered-state reply: {powered}')
    return [str(kind), str(tick), str(action), str(powered == 'Test passed').lower(),
            f'{rpm(gear):.4f}', f'{rpm(shaft):.4f}']

def verify_timing(args):
    expected = java_rows("clutch-gearshift-timing")
    with fixture_world(args, 'OrdinaryTransmission', pack=args.pack) as control:
        control.commands(('/fill 4 100 -16 14 100 -5 minecraft:smooth_stone', '/fill 4 101 -16 14 106 -5 minecraft:air', '/setblock 11 103 -10 minecraft:stone', '/tp @s 11.5 104 -9.5'))
        for kind, (x,y,z) in enumerate(RIGS):
            block = ('clutch', 'gearshift')[kind]
            control.commands((
                f'/setblock {x-1} {y} {z} create:creative_motor[facing=east]',
                f'/data merge block {x-1} {y} {z} {{ScrollValue:32}}',
                f'/setblock {x} {y} {z} create:{block}[axis=x,powered=false]',
                f'/setblock {x+1} {y} {z} create:shaft[axis=x]',
                f'/setblock {x} {y+1} {z} minecraft:lever[face=floor,facing=east,powered=false]',
            ))
        for _ in range(4):
            control.step_to(control.clock() + 1)
        start = control.clock()
        observed = []
        for tick in range(23):
            if tick:
                control.step_to(start + tick)
            for kind, (x,y,z) in enumerate(RIGS):
                observed.append(sample(control, kind, tick, 0))
                if tick in CHANGE:
                    control.call('interact', x, y+1, z, 'up')
                    lever = control.call('block', x, y+1, z)['state']
                    assert ('powered=true' in lever) == CHANGE[tick], (tick, kind, lever)
                    observed.append(sample(control, kind, tick, 1))
    compare("Ordinary Clutch and Gearshift", expected, observed)


def verify_competing(args):
    expected = java_rows("clutch-competing")
    observed = []
    with fixture_world(args, 'ClutchCompeting', pack=args.pack) as world:
        world.commands((
            '/fill 4 100 -16 14 100 -5 minecraft:smooth_stone',
            '/fill 4 101 -16 14 106 -5 minecraft:air',
            '/setblock 11 103 -10 minecraft:stone',
            '/tp @s 11.5 104 -9.5',
            '/setblock 7 102 -10 create:creative_motor[facing=east]',
            '/data merge block 7 102 -10 {ScrollValue:32}',
            '/setblock 8 102 -10 create:clutch[axis=x,powered=false]',
            '/setblock 9 102 -10 create:shaft[axis=x]',
            '/setblock 8 103 -10 minecraft:lever[face=floor,facing=east,powered=false]',
            '/gamemode survival',
            '/item replace entity @s hotbar.0 with create:wrench',
        ))
        for _ in range(4):
            world.step_to(world.clock() + 1)
        start = world.clock()
        for tick in range(len(expected)):
            if tick:
                world.step_to(start + tick)
            if tick in (4, 14):
                world.call('interact', 8, 103, -10, 'up')
            if tick == 10:
                world.command('/tp @s 5.5 101 -9.5')
                world.call('wait', 3)
                world.call('select', 'create:wrench')
                world.call('key', 'shift', 'down')
                world.call('wait', 4)
                try:
                    world.call('look-at', 7.5, 102.5, -9.5)
                    world.call('wait', 2)
                    hit = world.call('looking-at').get('block')
                    assert hit and hit['pos'] == [7, 102, -10], hit
                    world.call('mouse', 'right', 'click')
                    world.call('wait', 3)
                finally:
                    world.call('key', 'shift', 'up')
                assert world.call('block', 7, 102, -10)['block'] == 'minecraft:air'
                world.command('/tp @s 11.5 104 -9.5')
                world.call('wait', 3)
            state = world.call('block', 8, 102, -10)['state']
            values = world.commands(tuple(f'/data get block {x} 102 -10' for x in (7, 8, 9)))
            observed.append([str(tick), 'true' if 'powered=true' in state else 'false', *(f'{rpm(value):.4f}' for value in values)])
            if tick == 5:
                # Its configured output enters the sampled network at tick 6.
                world.commands((
                    '/setblock 9 102 -10 create:creative_motor[facing=west]',
                    '/data merge block 9 102 -10 {ScrollValue:64}',
                ))
    compare("Powered Clutch input retention, removal, and reattachment", expected, observed)


def transmission_drops(world, block, pos, *, radius=1.5):
    items = world.call('entities', 16, 'minecraft:item')['entities']
    return sum(item['item']['count'] for item in items
               if item['item']['item'] == f'create:{block}'
               and all(abs(point - (origin + .5)) < radius
                       for point, origin in zip(item['pos'], pos, strict=True)))


def break_effects(fixture, block):
    with (ROOT / 'fixtures/transmission-break-effects-java.csv').open(newline='') as source:
        events = [event for event in csv.DictReader(source)
                  if event['fixture'] == fixture and event['block'] == f'create:{block}']
    assert events and all(event['level_event'] == '2001' for event in events)
    return events


def verify_reconnect(args):
    expected = java_rows("clutch-gearshift-reconnect")
    observed = []
    lanes = (-12, -8)
    (effect,) = break_effects('reconnect', 'clutch')
    clutch_cue = effect['sound']
    with fixture_world(args, "ClutchGearshiftReconnect", pack=args.pack, env=TEST_AUDIO) as world:
        world.commands((
            '/fill 4 100 -16 14 100 -5 minecraft:smooth_stone',
            '/fill 4 101 -16 14 106 -5 minecraft:air',
            '/setblock 5 103 -10 minecraft:stone',
            '/tp @s 5.5 104 -9.5',
            *(command for z in lanes for command in (
                f'/setblock 7 102 {z} create:creative_motor[facing=east]',
                f'/data merge block 7 102 {z} {{ScrollValue:32}}',
                f'/setblock 8 102 {z} create:clutch[axis=x,powered=false]',
                f'/setblock 8 103 {z} minecraft:stone',
                f'/setblock 8 104 {z} minecraft:lever[face=floor,facing=east,powered=false]',
            )),
        ))
        for _ in range(4):
            world.step_to(world.clock() + 1)
        before_sounds = world.call('status')['heard'].get(clutch_cue, 0)
        start = world.clock()
        for tick in range(13):
            if tick:
                world.step_to(start + tick)
            for lane, z in enumerate(lanes):
                if tick in (3, 8):
                    world.command(f'/tp @s 8.5 105.5 {z + .5}')
                    world.call('interact', 8, 104, z, 'up')
                    world.call('wait', 2)
                    assert world.clock() == start + tick, (lane, tick)
                if tick == 5:
                    if lane:
                        world.command(f'/setblock 9 101 {z} minecraft:redstone_block')
                    world.commands((
                        f'/setblock 9 102 {z} create:gearshift[axis=x,powered={str(bool(lane)).lower()}]',
                        f'/setblock 10 102 {z} create:creative_motor[facing=west]',
                        f'/data merge block 10 102 {z} {{ScrollValue:64}}',
                    ))
                gate = world.call('block', 8, 102, z)
                gear = world.call('block', 9, 102, z)
                clutch = ('missing' if gate['block'] == 'minecraft:air' else
                          'open' if gate['state'] == 'create:clutch[axis=x,powered=true]' else
                          'closed' if gate['state'] == 'create:clutch[axis=x,powered=false]' else gate['state'])
                reverse = ('missing' if gear['block'] == 'minecraft:air' else
                           gear['state'].removeprefix('create:gearshift[axis=x,powered=').removesuffix(']'))
                speeds = world.commands(f'/data get block {x} 102 {z}' for x in (7, 8, 9, 10))
                drops = transmission_drops(world, 'clutch', (8, 102, z))
                observed.append([str(lane), str(tick), clutch, reverse, *(f'{rpm(data):.9g}' for data in speeds), str(drops)])
        gearshift_breaks = []
        heard = world.call('status')['heard'].get(clutch_cue, 0) - before_sounds
        for z in lanes:
            before = world.call('block', 9, 102, z)['state']
            result = world.command(f'/setblock 9 102 {z} minecraft:air destroy')
            gearshift_breaks.append(('powered=true' in before, result.startswith('Changed the block at ')))
        world.step_to(start + 13)
        gearshift_drops = [
            [str(lane), str(powered).lower(), str(destroyed).lower(),
             str(world.call('block', 9, 102, z)['block'] == 'minecraft:air').lower(),
             str(transmission_drops(world, 'gearshift', (9, 102, z)))]
            for lane, (z, (powered, destroyed)) in enumerate(zip(lanes, gearshift_breaks, strict=True))
        ]
    trace = ROOT / '.local/clutch-gearshift-reconnect-horizon.csv'
    with trace.open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(('lane', 'tick', 'clutch', 'gearshift_powered', 'left_rpm', 'clutch_rpm', 'gearshift_rpm', 'right_rpm', 'clutch_drops'))
        writer.writerows(observed)
    compare("Clutch reconnect through Gearshift", expected, observed)
    expected_drops = java_rows("clutch-gearshift-drop")
    if gearshift_drops != expected_drops:
        raise RuntimeError(f"Gearshift drop outcomes differ (Java, Horizon): {expected_drops}, {gearshift_drops}")
    print("Both powered and unpowered Gearshifts broke and dropped one item, matching Java.")
    assert heard == 1, (clutch_cue, heard)
    print("The scheduled Clutch break matched the Java sound event.")


def offset_axis(pos, axis, distance):
    return tuple(value + (distance if index == axis else 0) for index, value in enumerate(pos))


def coordinates(pos):
    return ' '.join(map(str, pos))


def verify_consecutive(args):
    expected = java_rows("clutch-gearshift-consecutive")
    observed = []
    axes = ("east", "up", "south")
    rigs = [(kind, axis, (8 + 5 * axis, 105, -12 + 5 * kind))
            for kind in range(2) for axis in range(3)]
    with fixture_world(args, "TransmissionConsecutivePower", pack=args.pack) as world:
        world.commands((
            '/fill 5 101 -16 21 101 -4 minecraft:smooth_stone',
            '/fill 5 102 -16 21 109 -4 minecraft:air',
            '/tp @s 13.5 102 -9.5',
        ))
        for kind, axis, pos in rigs:
            drive = coordinates(offset_axis(pos, axis, -1))
            output = coordinates(offset_axis(pos, axis, 1))
            block = ('clutch', 'gearshift')[kind]
            world.commands((
                f'/setblock {drive} create:creative_motor[facing={axes[axis]}]',
                f'/data merge block {drive} {{ScrollValue:32}}',
                f'/setblock {coordinates(pos)} create:{block}[axis={"xyz"[axis]},powered=false]',
                f'/setblock {output} create:shaft[axis={"xyz"[axis]}]',
            ))
        for _ in range(4):
            world.step_to(world.clock() + 1)
        start = world.clock()
        for tick in range(10):
            if tick:
                world.step_to(start + tick)
            for kind, axis, pos in rigs:
                shift = coordinates(pos)
                output = coordinates(offset_axis(pos, axis, 1))
                for phase in range(2 if 3 <= tick <= 6 else 1):
                    if phase:
                        signal = offset_axis(pos, 2, -1) if axis == 0 else offset_axis(pos, 0, 1)
                        block = "redstone_block" if tick % 2 else "air"
                        world.command(f'/setblock {coordinates(signal)} minecraft:{block}')
                        world.call('wait', 2)
                        assert world.clock() == start + tick, (kind, axis, tick)
                    block = world.call('block', *pos)
                    gate_rpm, output_rpm = world.commands((
                        f'/data get block {shift}', f'/data get block {output}',
                    ))
                    power = 'true' if 'powered=true' in block['state'] else 'false'
                    observed.append([str(kind), "xyz"[axis], str(tick), str(phase), power,
                                     f'{rpm(gate_rpm):.9g}', f'{rpm(output_rpm):.9g}'])
    trace = ROOT / '.local/clutch-gearshift-consecutive-horizon.csv'
    with trace.open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(('kind', 'axis', 'tick', 'phase', 'powered', 'gate_rpm', 'output_rpm'))
        writer.writerows(observed)
    compare("Clutch and Gearshift consecutive redstone on X/Y/Z", expected, observed)


def verify_gearshift_reverse(args, place_powered=False):
    fixture = "gearshift-powered-placement" if place_powered else "gearshift-two-sources"
    expected = java_rows(fixture)
    observed = []
    placement_entities = []
    forward = ("east", "up", "south")
    backward = ("west", "down", "north")
    rigs = [(lane, axis, (8 + 5 * axis, 105, -12 + 5 * lane))
            for lane in range(2) for axis in range(3)]
    effects = break_effects('gearshift-scheduled', 'gearshift')
    assert len(effects) == 6
    cue = effects[0]['sound']
    cue_tick = int(effects[0]['tick'])
    assert all(effect['sound'] == cue and int(effect['tick']) == cue_tick for effect in effects)
    expected_break_sounds = len(effects) // 2
    world_name = "GearshiftPoweredPlacement" if place_powered else "GearshiftReverseTwoSources"
    with fixture_world(args, world_name, pack=args.pack, env=TEST_AUDIO) as world:
        world.commands((
            '/fill 5 101 -16 21 101 -4 minecraft:smooth_stone',
            '/fill 5 102 -16 21 109 -4 minecraft:air',
            '/tp @s 13.5 102 -9.5',
        ))
        if place_powered:
            world.command('/item replace entity @s hotbar.0 with create:gearshift 8')
        for lane, axis, pos in rigs:
            left = coordinates(offset_axis(pos, axis, -1))
            right = coordinates(offset_axis(pos, axis, 1))
            right_speed = 64 if lane else -64
            if place_powered:
                signal = offset_axis(pos, 2, -1) if axis == 0 else offset_axis(pos, 0, 1)
                world.command(f'/setblock {coordinates(signal)} minecraft:redstone_block')
            world.commands((
                f'/setblock {left} create:creative_motor[facing={forward[axis]}]',
                f'/data merge block {left} {{ScrollValue:32}}',
                f'/setblock {right} create:creative_motor[facing={backward[axis]}]',
                f'/data merge block {right} {{ScrollValue:{right_speed}}}',
            ))
        for _ in range(4):
            world.step_to(world.clock() + 1)
        if place_powered:
            world.call('select', 'create:gearshift')
        before_sounds = world.call('status')['heard'].get(cue, 0)
        start = world.clock()
        for tick in range(9):
            if tick:
                world.step_to(start + tick)
            for lane, axis, pos in rigs:
                if tick == 4:
                    signal = offset_axis(pos, 2, -1) if axis == 0 else offset_axis(pos, 0, 1)
                    if place_powered:
                        x, y, z = pos
                        feet = (x + .5, y - 1, z + 2.5) if axis == 0 else (x - 2.5, y - 1, z + .5)
                        world.command(f'/tp @s {coordinates(feet)}')
                        world.call('wait', 2)
                        world.call('interact', *signal, 'south' if axis == 0 else 'west')
                    else:
                        world.commands((
                            f'/setblock {coordinates(pos)} create:gearshift[axis={"xyz"[axis]},powered=false]',
                            f'/setblock {coordinates(signal)} minecraft:redstone_block',
                        ))
                    world.call('wait', 2)
                    assert world.clock() == start + tick, (lane, axis, tick)
                block = world.call('block', *pos)
                if tick == 4:
                    assert block['state'] == f'create:gearshift[axis={"xyz"[axis]},powered=true]', block
                power = ('missing' if block['block'] == 'minecraft:air' else
                         'true' if 'powered=true' in block['state'] else 'false')
                speeds = world.commands(f'/data get block {coordinates(offset_axis(pos, axis, end))}'
                                        for end in (-1, 0, 1))
                if place_powered:
                    placement_entities.append({"lane": lane, "axis": "xyz"[axis], "tick": tick,
                                               "state": block['state'], "block_data": speeds[1]})
                drops = transmission_drops(world, 'gearshift', pos)
                observed.append([str(lane), "xyz"[axis], str(tick), power,
                                 *(f'{rpm(data):.9g}' for data in speeds), str(drops)])
            heard = world.call('status')['heard'].get(cue, 0) - before_sounds
            assert heard == (expected_break_sounds if tick >= cue_tick else 0), (cue, tick, heard)
    trace = ROOT / f'.local/{fixture}-horizon.csv'
    with trace.open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(('lane', 'axis', 'tick', 'powered', 'left_rpm', 'gearshift_rpm', 'right_rpm', 'gearshift_drops'))
        writer.writerows(observed)
    if place_powered:
        entities = ROOT / '.local/gearshift-powered-placement-horizon-entities.jsonl'
        entities.write_text(''.join(json.dumps(row) + '\n' for row in placement_entities))
    compare("Powered Gearshift hand placement" if place_powered else "Gearshift reversal between two live drives",
            expected, observed)
    print(f"Matched {expected_break_sounds} Java scheduled Gearshift break sound events on tick {cue_tick}.")
    if place_powered:
        expected_entities = [[*row[:6], row[8]] for row in java_rows("gearshift-powered-placement-entities")]
        actual_entities = []
        for row in placement_entities:
            axis = row['axis']
            data = row['block_data']
            present = 'id: "create:gearshift"' in data
            source = re.search(r'\bShaftInputSide: (-?\d+)', data)
            side = int(source[1]) if source else 0
            facing = forward["xyz".index(axis)] if side > 0 else backward["xyz".index(axis)] if side < 0 else '-'
            actual_entities.append([str(row['lane']), axis, str(row['tick']), str(present).lower(),
                                    axis if present else '-', facing, f'{rpm(data):.9g}'])
        compare("Powered Gearshift block entities and source facing", expected_entities, actual_entities)


def verify_cold_reopen(args):
    expected = java_rows("clutch-gearshift-cold-reopen")
    observed = []
    rigs = (
        ('clutch', False, True, (8, 102, -12)),
        ('clutch', True, True, (8, 102, -8)),
        ('gearshift', False, True, (13, 102, -12)),
        ('gearshift', True, True, (13, 102, -8)),
        ('clutch', False, False, (8, 102, -5)),
        ('gearshift', False, False, (13, 102, -5)),
    )

    def sample(world, phase, tick):
        for rig, (_, _, driven, pos) in enumerate(rigs):
            x, y, z = pos
            block = world.call('block', *pos)
            if not driven:
                assert world.call('block', x - 1, y, z)['block'] == 'minecraft:air'
            voltage = 'true' if 'powered=true' in block['state'] else 'false'
            gate, output = world.commands((
                f'/data get block {x} {y} {z}',
                f'/data get block {x + 1} {y} {z}',
            ))
            if not driven:
                assert f'id: "{block["block"]}"' in gate, gate
                assert 'id: "create:simple_kinetic"' in output, output
            facing = ('west' if re.search(r'\bShaftInputSide: -1\b', gate) else
                      'east' if re.search(r'\bShaftInputSide: 1\b', gate) else '-')
            observed.append([phase, str(rig), str(tick), block['block'], voltage,
                             f'{rpm(gate):.9g}', f'{rpm(output):.9g}', facing])

    with fixture_world(args, "TransmissionColdReopen", pack=args.pack) as world:
        world.commands((
            '/fill 4 100 -15 16 100 -5 minecraft:smooth_stone',
            '/fill 4 101 -15 16 106 -5 minecraft:air',
            '/tp @s 11.5 101 -9.5',
        ))
        for block, powered, driven, (x, y, z) in rigs:
            if powered:
                world.command(f'/setblock {x} {y + 1} {z} minecraft:redstone_block')
            world.commands((
                f'/setblock {x} {y} {z} create:{block}[axis=x,powered={str(powered).lower()}]',
                f'/setblock {x + 1} {y} {z} create:shaft[axis=x]',
            ))
            if driven:
                world.commands((
                    f'/setblock {x - 1} {y} {z} create:creative_motor[facing=east]',
                    f'/data merge block {x - 1} {y} {z} {{ScrollValue:32}}',
                ))
        for _ in range(8):
            world.step_to(world.clock() + 1)
        sample(world, "write", 7)
        world.restart()
        start = world.clock()
        for tick in range(8):
            if tick:
                world.step_to(start + tick)
            sample(world, "read", tick)
    trace = ROOT / '.local/clutch-gearshift-cold-reopen-horizon.csv'
    with trace.open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(('phase', 'rig', 'tick', 'block', 'powered', 'gate_rpm', 'shaft_rpm', 'source'))
        writer.writerows(observed)
    compare("Cold-reopened Clutch and Gearshift", expected, observed)


def speeds(host):
    return tuple(map(rpm, host.commands(('/data get block 8 102 -10', '/data get block 9 102 -10'))))


def state(controller, powered):
    return controller.call('block', *BLOCK)['state'] == f'create:gearshift[axis=x,powered={str(powered).lower()}]'


def verify_lan(args, scratch):
    spec = spec_from_file_location("multiplayer_fixture", ROOT / "tools/test-multiplayer.py")
    multiplayer = module_from_spec(spec)
    spec.loader.exec_module(multiplayer)
    guest_name = "GearshiftLever"
    with fixture_world(args, 'GearshiftLeverLAN', pack=args.pack) as host:
        host.commands((
            '/fill 4 100 -14 14 100 -5 minecraft:smooth_stone',
            '/fill 4 101 -13 14 106 -6 minecraft:air',
            '/setblock 11 103 -10 minecraft:stone',
            '/setblock 5 103 -10 minecraft:stone',
            '/setblock 7 102 -10 create:creative_motor[facing=east]',
            '/data merge block 7 102 -10 {ScrollValue:32}',
            '/setblock 8 102 -10 create:gearshift[axis=x,powered=false]',
            '/setblock 9 102 -10 create:shaft[axis=x]',
            '/setblock 8 103 -10 minecraft:lever[face=floor,facing=east,powered=false]',
            '/tp @s 11.5 104 -9.5',
        ))
        for _ in range(4):
            host.step_to(host.clock() + 1)
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(args, scratch, address, guest_name, scenario='gearshift-lever', pack=args.pack) as guest:
            multiplayer.until('guest to enter the driven world', lambda: any(
                user['name'] == guest_name and user['placed'] for user in host.call('lan', 'status')['guests']
            ))
            host.commands((f'/gamemode survival {guest_name}', f'/tp {guest_name} 5.5 104 -9.5'))
            multiplayer.until('guest to see the original drive state', lambda: (
                guest.call('state')['player']['position'] == [5.5, 104, -9.5] and state(guest, False)
            ))
            assert speeds(host) == (32, 32), speeds(host)
            start = host.clock()
            action = host.call('interact', *LEVER, 'up')
            if not state(host, True):
                raise RuntimeError(f'Host action left lever and gearshift as {host.call("block", *LEVER)}, {host.call("block", *BLOCK)}. Observed {speeds(host)} from {action}.')
            multiplayer.until('guest to see rising power', lambda: state(guest, True))
            assert host.clock() == start and speeds(host) == (32, 0), speeds(host)
            host.step_to(start + 1)
            assert speeds(host) == (32, -32), speeds(host)
            guest.call('interact', *LEVER, 'up')
            multiplayer.until('host to process falling power', lambda: state(host, False))
            multiplayer.until('guest to see falling power', lambda: state(guest, False))
            assert host.clock() == start + 1 and speeds(host) == (32, 0), speeds(host)
            host.step_to(start + 2)
            assert speeds(host) == (32, 32), speeds(host)
    print('Host and guest lever clicks matched both Java action ticks and the following RPM changes.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--competing", action="store_true")
    mode.add_argument("--reconnect", action="store_true")
    mode.add_argument("--consecutive", action="store_true")
    mode.add_argument("--gearshift-reverse", action="store_true")
    mode.add_argument("--gearshift-powered-placement", action="store_true")
    mode.add_argument("--cold-reopen", action="store_true")
    mode.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-gl-") as scratch:
            verify_lan(args, Path(scratch))
    elif args.competing:
        verify_competing(args)
    elif args.reconnect:
        verify_reconnect(args)
    elif args.consecutive:
        verify_consecutive(args)
    elif args.gearshift_reverse:
        verify_gearshift_reverse(args)
    elif args.gearshift_powered_placement:
        verify_gearshift_reverse(args, place_powered=True)
    elif args.cold_reopen:
        verify_cold_reopen(args)
    else:
        verify_timing(args)


if __name__ == "__main__":
    main()
