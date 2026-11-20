#!/usr/bin/env python3
"""Change two initialized transmissions and reopen before their next simulation tick."""

import argparse
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world, last_command_message, run_command_harness

timing = import_module('test-transmission-timing')
LANES = (-12, -5)


def sample(world, phase, block, motor_x):
    rows = []
    for lane, z in enumerate(LANES):
        pos = (8, 102, z)
        state = world.call('block', *pos)
        power = ('missing' if state['block'] == 'minecraft:air'
                 else str('powered=true' in state['state']).lower())
        speeds = world.commands(f'/data get block {x} 102 {z}' for x in (motor_x[0], 8, motor_x[1]))
        motors = [(x, 102, z) for x in (motor_x if block == 'gearshift' else motor_x[1:])]
        present = [str(world.call('block', *at)['block'] == 'create:creative_motor').lower()
                   for at in motors]
        drops = timing.transmission_drops(world, block, pos, radius=2)
        motor_drops = timing.transmission_drops(world, 'creative_motor', pos, radius=3)
        rows.append([phase, str(lane), power, *(f'{timing.rpm(data):.9g}' for data in speeds),
                     str(drops), *present, str(motor_drops)])
    return rows


def first_ticks(args, world, name, block, motor_x, saved):
    world.stop()
    operations = [{'op': 'settle'}]
    for tick in range(3):
        if tick:
            operations.append({'op': 'tick', 'n': 1})
        operations.append({'op': 'cmd', 'cmd': '/time query gametime'})
        for z in LANES:
            operations.extend({'op': 'cmd', 'cmd': command} for command in (
                f'/execute if block 8 102 {z} create:{block}[powered=true]',
                *(f'/data get block {x} 102 {z}' for x in (motor_x[0], 8, motor_x[1])),
            ))
    records = run_command_harness(args, world.socket.parent / 'game', name, operations, env=world.env)
    replies = iter(map(last_command_message, records))
    observed = []
    for tick in range(3):
        assert int(next(replies).split()[-2]) == saved + tick
        for lane in range(2):
            power = next(replies)
            assert power in ('Test passed', 'Test failed'), power
            first, gate, second = [next(replies) for _ in range(3)]
            assert f'id: "create:{block}"' in gate, gate
            assert (f'TransmissionReconnectPending: {saved}L' in gate) == (tick == 0), gate
            motors = (first, second) if block == 'gearshift' else (second,)
            present = [str('id: "create:motor"' in data).lower() for data in motors]
            observed.append([str(lane), str(tick), str(power == 'Test passed').lower(),
                             *(f'{timing.rpm(data):.9g}' for data in (first, gate, second)), *present])
    assert next(replies, None) is None
    return observed


def verify(args):
    snapshots = {}
    drop_rule = 'off' if args.drops_off else 'on'
    block = 'gearshift' if args.gearshift else 'clutch'
    fields = ('phase', 'lane', 'powered', 'left_rpm', f'{block}_rpm', 'right_rpm',
              f'{block}_drops', *(('left_motor',) if args.gearshift else ()), 'right_motor', 'motor_drops')
    suffix = '-mirrored' if args.mirror else ''
    motor_x = (9, 7) if args.mirror else (7, 9)
    facing = ('west', 'east') if args.mirror else ('east', 'west')
    startup_expected = []
    startup_fields = ('lane', 'phase_tick', 'powered', 'left_rpm', f'{block}_rpm', 'right_rpm',
                      *(('left_motor',) if args.gearshift else ()), 'right_motor')
    with (ROOT / 'fixtures' / f'{block}-pending-reopen{suffix}-java.csv').open(newline='') as source:
        for row in csv.DictReader(source):
            if row['drops_rule'] == drop_rule and row['phase'] == 'read' and int(row['phase_tick']) <= 2:
                startup_expected.append([row[field] for field in startup_fields])
            if (row['drops_rule'] == drop_rule
                and (row['phase'], row['phase_tick']) in (('write', '8'), ('read', '48'))):
                snapshots.setdefault(row['phase'], []).append([row[field] for field in fields])
    assert len(snapshots['write']) == len(snapshots['read']) == 2
    name = f'{block.title()}PendingReopen{"NoDrops" if args.drops_off else ""}'
    drops_enabled = str(not args.drops_off).lower()
    with fixture_world(args, name, pack=args.pack) as world:
        world.commands((
            f'/gamerule minecraft:block_drops {drops_enabled}',
            '/fill 4 101 -15 14 106 -3 minecraft:air',
            '/fill 4 100 -15 14 100 -3 minecraft:smooth_stone',
            '/tp @s 10.5 101 -8.5',
        ))
        for lane, z in enumerate(LANES):
            powered = args.gearshift and lane == 1
            if powered:
                world.command(f'/setblock 8 103 {z} minecraft:redstone_block')
            world.commands((
                f'/setblock 8 102 {z} create:{block}[axis=x,powered={str(powered).lower()}]',
                f'/setblock {motor_x[0]} 102 {z} create:creative_motor[facing={facing[0]}]',
                f'/data merge block {motor_x[0]} 102 {z} {{ScrollValue:32}}',
            ))
        for _ in range(4):
            world.step_to(world.clock() + 1)
        start = world.clock()
        for tick in range(1, 9):
            world.step_to(start + tick)
            for lane, z in enumerate(LANES):
                if tick == 3 and not args.gearshift:
                    world.command(f'/setblock 8 103 {z} minecraft:redstone_block')
                if tick == 5:
                    rpm = 64 if lane == 0 else -64
                    if args.gearshift:
                        rpm = -rpm
                    world.commands((
                        f'/setblock {motor_x[1]} 102 {z} create:creative_motor[facing={facing[1]}]',
                        f'/data merge block {motor_x[1]} 102 {z} {{ScrollValue:{rpm}}}',
                    ))
                if tick == 8:
                    signal = 'redstone_block' if args.gearshift and lane == 0 else 'air'
                    world.command(f'/setblock 8 103 {z} minecraft:{signal}')
        saved = world.clock()
        assert saved == start + 8
        observed = sample(world, 'write', block, motor_x)
        pending = world.commands(f'/data get block 8 102 {z}' for z in LANES)
        assert all(f'TransmissionDetachTime: {saved}L' in data for data in pending), pending
        assert world.clock() == saved
        if args.first_ticks:
            assert observed == snapshots['write']
            actual = first_ticks(args, world, name, block, motor_x, saved)
            trace = ROOT / f'.local/{block}-first-startup{suffix}-horizon.csv'
            with trace.open('w', newline='') as output:
                writer = csv.writer(output)
                writer.writerow(startup_fields)
                writer.writerows(actual)
            timing.compare(f'First {block} startup ticks{suffix}', startup_expected, actual)
            return
        world.restart()
        assert world.command('/gamerule minecraft:block_drops').endswith(f' {drops_enabled}')
        for _ in range(3):
            world.step_to(world.clock() + 1)
        for _ in range(3):
            observed.extend(sample(world, 'read', block, motor_x))
            world.step_to(world.clock() + 1)
    trace = ROOT / f'.local/{block}-pending-reopen-{drop_rule}-horizon.csv'
    with trace.open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(fields)
        writer.writerows(observed)
    timing.compare(f'Pending {block.title()} reconnect after cold reopen with drops {drop_rule}',
                   snapshots['write'] + snapshots['read'] * 3, observed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    parser.add_argument('--gearshift', action='store_true')
    parser.add_argument('--drops-off', action='store_true')
    parser.add_argument('--first-ticks', action='store_true')
    parser.add_argument('--mirror', action='store_true')
    args = parser.parse_args()
    if args.mirror and (not args.first_ticks or args.drops_off):
        parser.error('--mirror requires --first-ticks with block drops enabled')
    verify(args)
