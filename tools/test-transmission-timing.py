#!/usr/bin/env python3
"""Compare ordinary Clutch and Gearshift redstone timing with the pinned Java fixtures."""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

CHANGE = {5: True, 9: False, 13: True, 17: False}
RIGS = ((8, 102, -12), (8, 102, -8))
LEVER = (8, 103, -10)
BLOCK = (8, 102, -10)


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
    with fixture_world(args, 'ClutchCompeting', render=True, pack=args.pack) as world:
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


def speeds(host):
    return tuple(map(rpm, host.commands(('/data get block 8 102 -10', '/data get block 9 102 -10'))))


def state(controller, powered):
    return controller.call('block', *BLOCK)['state'] == f'create:gearshift[axis=x,powered={str(powered).lower()}]'


def verify_lan(args, scratch):
    spec = spec_from_file_location("multiplayer_fixture", ROOT / "tools/test-multiplayer.py")
    multiplayer = module_from_spec(spec)
    spec.loader.exec_module(multiplayer)
    guest_name = "GearshiftLever"
    with fixture_world(args, 'GearshiftLeverLAN', render=True, pack=args.pack) as host:
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
        with multiplayer.joined_client(args, scratch, address, guest_name, render=True, scenario='gearshift-lever', pack=args.pack) as guest:
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
    mode.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-gl-") as scratch:
            verify_lan(args, Path(scratch))
    elif args.competing:
        verify_competing(args)
    else:
        verify_timing(args)


if __name__ == "__main__":
    main()
