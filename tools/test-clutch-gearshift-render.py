#!/usr/bin/env python3
"""Compare the two submitted shaft halves with Java's actual per-side RPM."""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from hashlib import sha256
from math import fmod, isclose
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

MARKER = 'CREATE_SPLIT_SHAFT_FRAME '
RIGS = ((8, 102, -12), (8, 102, -7))
CHANGE = {5: True, 9: False, 13: True, 17: False}
ASSETS = {
    "assets/create/models/block/shaft_half.json": "bbd1d6226933a4b29b365a449e87ecff1f851965f82f802c0800747b530a0576",
    "assets/create/models/block/clutch/block.json": "61f2aa44a042ae298aa71e989066f2d77851e4501cfcc0f9c11491b01eda32bf",
    "assets/create/models/block/gearshift/block.json": "4d2b153d6d0249ce65fbe5d3423580caacd9c595e58c5d6138bfceea738ae3aa",
}


def asset(args):
    with ZipFile(args.pack or ROOT / ".local/create.hmod") as archive:
        for model, expected in ASSETS.items():
            if sha256(archive.read(model)).hexdigest() != expected:
                raise RuntimeError(f"Changed Java model {model}.")


def sample(log, pos, clock, powered, left, right, phase, *, after=0):
    boundary = monotonic() + 3
    last = None
    while monotonic() < boundary:
        for line in reversed(log.read_bytes()[after:].decode(errors="replace").splitlines()):
            if not line.startswith(MARKER):
                continue
            row = line[len(MARKER):].split(',')
            if len(row) != 16:
                continue
            x, y, z, _, axis, state, source, tick, partial, angle_phase, neg, pos_rpm, neg_angle, pos_angle, n_vertices, p_vertices = row
            if tuple(map(int, (x, y, z))) != pos or (clock is not None and int(tick) != clock) or state != str(powered).lower():
                continue
            last = row
            if (float(neg), float(pos_rpm), float(angle_phase)) != (left, right, phase):
                continue
            if axis != '0' or source != '-1' or min(int(n_vertices), int(p_vertices)) <= 0:
                raise RuntimeError(f'Shaft-half frame has an incorrect axis, source, or missing draws: {row}')
            time = int(tick) + float(partial)
            for side, speed, angle in (('west', left, neg_angle), ('east', right, pos_angle)):
                expected = fmod(time * speed * 3 / 10, 360) + phase
                error = (float(angle) - expected + 180) % 360 - 180
                if not isclose(error, 0.0, abs_tol=0.0002):
                    raise RuntimeError(f'{pos}, {side} shaft angle on tick {clock}. Java {expected}, Horizon {angle}.')
            return float(partial)
        sleep(0.05)
    raise RuntimeError(f'Expected both Java shaft halves at {pos}, tick {clock}, powered {powered}, RPM {left}/{right}. Last matching frame {last}.')


def verify(args):
    with (ROOT / "fixtures/clutch-gearshift-render-java.csv").open(newline="") as ref:
        references = {
            (int(row["block_index"]), int(row["tick"]), int(row["after_click"])):
                (float(row["phase"]), float(row["west_rpm"]), float(row["east_rpm"]))
            for row in csv.DictReader(ref)
        }
    assert len(references) == 54
    asset(args)
    partials = set()
    with fixture_world(args, 'SplitShaftRender', render=True, pack=args.pack,
                       env={'CREATE_SPLIT_SHAFT_RENDER': '1'}) as control:
        control.commands((
            '/fill 4 100 -16 14 100 -5 minecraft:smooth_stone',
            '/fill 4 101 -16 14 106 -5 minecraft:air',
            '/fill 11 103 -10 11 103 -9 minecraft:stone',
            '/tp @s 11.3 104 -9.0',
        ))
        for kind, (x, y, z) in enumerate(RIGS):
            block = ('clutch', 'gearshift')[kind]
            control.commands((
                f'/setblock {x-1} {y} {z} create:creative_motor[facing=east]',
                f'/data merge block {x-1} {y} {z} {{ScrollValue:32}}',
                f'/setblock {x} {y} {z} create:{block}[axis=x,powered=false]',
                f'/setblock {x+1} {y} {z} create:shaft[axis=x]',
                f'/setblock {x} {y+1} {z} minecraft:lever[face=floor,facing=east,powered=false]',
            ))
        for _ in range(4):
            control.step_to(control.clock()+1)
        start = control.clock()
        powered = False
        for tick in range(23):
            if tick:
                control.step_to(start+tick)
            for kind, pos in enumerate(RIGS):
                x, y, z = pos
                control.call('look-at', x + 0.5, y + 0.5, z + 0.5)
                phase, left, right = references[kind, tick, 0]
                partials.add(sample(control.socket.parent/'ctl.log', pos, start+tick, powered, left, right, phase))
                if tick in CHANGE:
                    control.call('interact', x, y+1, z, 'up')
                    control.call('look-at', x + 0.5, y + 0.5, z + 0.5)
                    phase, left, right = references[kind, tick, 1]
                    partials.add(sample(control.socket.parent/'ctl.log', pos, start+tick, CHANGE[tick], left, right, phase))
            if tick in CHANGE:
                powered = CHANGE[tick]
            if args.frames and tick in (5, 9):
                args.frames.mkdir(parents=True, exist_ok=True)
                control.call('screenshot', str(args.frames / f'gearshift-{tick}.png'))
    if len(partials) < 2:
        raise RuntimeError(f'Expected several animation fractions, found {partials}.')
    print(f'Both Clutch and Gearshift shaft halves match all {len(references)} Java rendered states at {len(partials)} submitted render fractions.')


def check_frame(client, powered, right_rpm, *, after=0):
    client.call('look-at', 8.5, 102.5, -9.5)
    sample(client.socket.parent / 'ctl.log', (8, 102, -10), None, powered, 32.0, right_rpm, 22.5, after=after)


def verify_lan(args, scratch):
    spec = spec_from_file_location("multiplayer_fixture", ROOT / "tools/test-multiplayer.py")
    multiplayer = module_from_spec(spec)
    spec.loader.exec_module(multiplayer)
    guest_name = "ShaftRender"
    lever = (8, 103, -10)
    os.environ['CREATE_SPLIT_SHAFT_RENDER'] = '1'
    with fixture_world(args, 'SplitShaftLAN', render=True, pack=args.pack) as host:
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
        with multiplayer.joined_client(args, scratch, address, guest_name, render=True, scenario='split-shaft-render', pack=args.pack) as guest:
            multiplayer.until('guest to enter the driven world', lambda: any(
                user['name'] == guest_name and user['placed'] for user in host.call('lan', 'status')['guests']
            ))
            host.commands((f'/gamemode survival {guest_name}', f'/tp {guest_name} 5.5 104 -9.5'))
            multiplayer.until('guest to see the unpowered Gearshift', lambda: (
                guest.call('state')['player']['position'] == [5.5, 104.0, -9.5]
                and 'powered=false' in guest.call('block', *(8, 102, -10))['state']
            ))
            check_frame(host, False, 32.0)
            check_frame(guest, False, 32.0)
            clock = host.clock()
            peers = (host, guest)
            after = [(peer.socket.parent / 'ctl.log').stat().st_size for peer in peers]
            host.call('interact', *lever, 'up')
            for peer, offset in zip(peers, after, strict=True):
                check_frame(peer, True, -32.0, after=offset)
            assert host.clock() == clock
            host.step_to(clock + 1)
            after = [(peer.socket.parent / 'ctl.log').stat().st_size for peer in peers]
            guest.call('interact', *lever, 'up')
            for peer, offset in zip(peers, after, strict=True):
                check_frame(peer, False, 32.0, after=offset)
            assert host.clock() == clock + 1
    print('Both clients submitted two original shaft halves with correct Java RPM before, on each lever action, and after returning to forward rotation.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--frames", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-srl-") as scratch:
            verify_lan(args, Path(scratch))
    else:
        verify(args)


if __name__ == "__main__":
    main()
