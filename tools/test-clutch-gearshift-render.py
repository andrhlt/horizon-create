#!/usr/bin/env python3
"""Compare the two submitted shaft halves with Java's actual per-side RPM."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
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
multiplayer = import_module('test-multiplayer')
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


def sample(log, pos, clock, powered, left, right, phase, *, after=0, block=None,
           axis_index=0, input_side=-1):
    boundary = monotonic() + 3
    last = None
    while monotonic() < boundary:
        for line in reversed(log.read_bytes()[after:].decode(errors="replace").splitlines()):
            if not line.startswith(MARKER):
                continue
            row = line[len(MARKER):].split(',')
            if len(row) != 16:
                continue
            x, y, z, drawn, axis, state, source, tick, partial, angle_phase, neg, pos_rpm, neg_angle, pos_angle, n_vertices, p_vertices = row
            if block is not None and drawn != block:
                continue
            if tuple(map(int, (x, y, z))) != pos or (clock is not None and int(tick) != clock) or state != str(powered).lower():
                continue
            last = row
            if (float(neg), float(pos_rpm), float(angle_phase)) != (left, right, phase):
                continue
            if (int(axis) != axis_index or int(source) != input_side
                or min(int(n_vertices), int(p_vertices)) <= 0):
                raise RuntimeError(f'Shaft-half frame has an incorrect axis, source, or missing draws: {row}')
            time = int(tick) + float(partial)
            for side, speed, angle in (('negative', left, neg_angle), ('positive', right, pos_angle)):
                expected = fmod(time * speed * 3 / 10, 360) + phase
                error = (float(angle) - expected + 180) % 360 - 180
                if not isclose(error, 0.0, abs_tol=0.0002):
                    raise RuntimeError(f'{pos}, {side} shaft angle on tick {clock}. Java {expected}, Horizon {angle}.')
            return float(partial)
        sleep(0.05)
    raise RuntimeError(f'Expected both Java shaft halves at {pos}, tick {clock}, powered {powered}, RPM {left}/{right}. Last matching frame {last}.')


def java_references():
    with (ROOT / "fixtures/clutch-gearshift-render-java.csv").open(newline="") as ref:
        references = {
            (int(row["block_index"]), int(row["tick"]), int(row["after_click"])):
                (float(row["phase"]), float(row["west_rpm"]), float(row["east_rpm"]))
            for row in csv.DictReader(ref)
        }
    assert len(references) == 54
    return references


def verify(args):
    references = java_references()
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


def verify_axes(args, scratch=None):
    timing = import_module('test-transmission-timing')
    negative_faces = ('west', 'down', 'north')
    positive_faces = ('east', 'up', 'south')
    with (ROOT / 'fixtures/transmission-render-axes-java.csv').open(newline='') as source:
        rows = list(csv.DictReader(source))
    asset(args)
    rigs = {}
    for row in rows:
        block_index, axis = int(row['block_index']), 'xyz'.index(row['axis'])
        side = -1 if row['input_face'] == negative_faces[axis] else 1
        face = positive_faces[axis] if side == 1 else negative_faces[axis]
        assert row['input_face'] == row['source'] == face, row
        key = (block_index, axis, side)
        if key in rigs:
            continue
        pos = [8 + 6 * axis, 103 + 10 * block_index + (5 if side == 1 else 0), -10]
        parity = sum(coordinate for index, coordinate in enumerate(pos) if index != axis) % 2
        phase = float(row['angle_offset'])
        if parity != (0 if phase == 22.5 else 1):
            pos[(axis + 2) % 3] += 1
        rigs[key] = tuple(pos)
    assert len(rigs) == 12 and len(rows) == 84
    xyz = timing.coordinates
    offset = timing.offset_axis
    devices = ('clutch', 'gearshift')
    frames = set()
    env = {'CREATE_SPLIT_SHAFT_RENDER': '1'}
    world_name = 'SplitShaftRenderAxesLAN' if scratch else 'SplitShaftRenderAxes'
    with ExitStack() as sessions:
        world = sessions.enter_context(fixture_world(args, world_name, render=True, pack=args.pack, env=env))
        world.commands((
            '/fill 4 100 -15 25 100 -4 minecraft:smooth_stone',
            '/fill 4 101 -15 25 125 -4 minecraft:air',
            '/tp @s 11.5 101 -7.5',
        ))
        for (block_index, axis, side), pos in rigs.items():
            block = devices[block_index]
            motor = xyz(offset(pos, axis, side))
            shaft = xyz(offset(pos, axis, -side))
            facing = negative_faces[axis] if side == 1 else positive_faces[axis]
            x, y, z = pos
            world.commands((
                f'/setblock {motor} create:creative_motor[facing={facing}]',
                f'/data merge block {motor} {{ScrollValue:32}}',
                f'/setblock {xyz(pos)} create:{block}[axis={"xyz"[axis]},powered=false]',
                f'/setblock {shaft} create:shaft[axis={"xyz"[axis]}]',
                f'/setblock {x+3} {y-2} {z+3} minecraft:stone',
            ))
        for _ in range(4):
            world.step_to(world.clock() + 1)
        viewer, player = world, '@s'
        if scratch:
            player = 'ShaftAxisGuest'
            address = f"127.0.0.1:{world.call('lan', 'open', '0', 'commands', 'force')['port']}"
            viewer = sessions.enter_context(multiplayer.joined_client(
                args, scratch, address, player, render=True, pack=args.pack, env=env,
                scenario='split-shaft-render-axes'))
            multiplayer.until('guest to enter the shaft axis world', lambda: any(
                user['name'] == player and user['placed'] for user in world.call('lan', 'status')['guests']
            ))
        start = world.clock()
        current = 0
        log = viewer.socket.parent / 'ctl.log'
        for row in rows:
            tick = int(row['tick'])
            for elapsed in range(current + 1, tick + 1):
                world.step_to(start + elapsed)
            current = tick
            block_index, axis = int(row['block_index']), 'xyz'.index(row['axis'])
            side = -1 if row['input_face'] == negative_faces[axis] else 1
            pos = rigs[block_index, axis, side]
            powered = row['powered'] == 'true'
            after = log.stat().st_size
            if row['phase'] == '1':
                signal = offset(pos, 0, -1) if axis == 1 else offset(pos, 1, 1)
                material = 'redstone_block' if powered else 'air'
                world.command(f'/setblock {xyz(signal)} minecraft:{material}')
            x, y, z = pos
            feet = (x + 3.5, y - 1, z + 3.5)
            world.command(f'/tp {player} {xyz(feet)}')
            if scratch:
                multiplayer.until('guest to reach the shaft viewing position', lambda:
                                  viewer.call('state')['player']['position'] == list(feet))
            viewer.call('look-at', x + .5, y + .5, z + .5)
            frames.add(sample(log, pos, None if scratch else start + tick, powered, float(row['negative_rpm']),
                              float(row['positive_rpm']), float(row['angle_offset']),
                              after=after, block=f'create:{devices[block_index]}', axis_index=axis,
                              input_side=side))
            assert world.clock() == start + tick
    fractions = ', '.join(f'{fraction:.3f}' for fraction in sorted(frames))
    print(f'Matched {len(rows)} Java split-shaft states and angles on X, Y and Z with both source faces '
          f'at frame fractions {fractions}.')


def check_frame(client, block, powered, rotation, *, after=0):
    _, left, right = rotation
    pos = (8, 102, -10)
    phase = 22.5 if (pos[1] + pos[2]) % 2 == 0 else 0.0
    client.call('look-at', 8.5, 102.5, -9.5)
    sample(client.socket.parent / 'ctl.log', pos, None, powered, left, right, phase,
           after=after, block=f'create:{block}')


def verify_lan(args, scratch):
    block = args.lan_block
    kind = ('clutch', 'gearshift').index(block)
    refs = java_references()
    asset(args)
    guest_name = "ShaftRender"
    lever = (8, 103, -10)
    os.environ['CREATE_SPLIT_SHAFT_RENDER'] = '1'
    world_name = 'ClutchShaftLAN' if block == 'clutch' else 'SplitShaftLAN'
    with fixture_world(args, world_name, render=True, pack=args.pack) as host:
        host.commands((
            '/fill 4 100 -14 14 100 -5 minecraft:smooth_stone',
            '/fill 4 101 -13 14 106 -6 minecraft:air',
            '/setblock 11 103 -10 minecraft:stone',
            '/setblock 5 103 -10 minecraft:stone',
            '/setblock 7 102 -10 create:creative_motor[facing=east]',
            '/data merge block 7 102 -10 {ScrollValue:32}',
            f'/setblock 8 102 -10 create:{block}[axis=x,powered=false]',
            '/setblock 9 102 -10 create:shaft[axis=x]',
            '/setblock 8 103 -10 minecraft:lever[face=floor,facing=east,powered=false]',
            '/tp @s 11.5 104 -9.5',
        ))
        for _ in range(4):
            host.step_to(host.clock() + 1)
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(args, scratch, address, guest_name, render=True, scenario=f'split-shaft-render-{block}', pack=args.pack) as guest:
            multiplayer.until('guest to enter the driven world', lambda: any(
                user['name'] == guest_name and user['placed'] for user in host.call('lan', 'status')['guests']
            ))
            host.commands((f'/gamemode survival {guest_name}', f'/tp {guest_name} 5.5 104 -9.5'))
            multiplayer.until(f'guest to see the unpowered {block}', lambda: (
                guest.call('state')['player']['position'] == [5.5, 104.0, -9.5]
                and guest.call('block', 8, 102, -10)['state'] == f'create:{block}[axis=x,powered=false]'
            ))
            check_frame(host, block, False, refs[kind, 5, 0])
            check_frame(guest, block, False, refs[kind, 5, 0])
            clock = host.clock()
            peers = (host, guest)
            after = [(peer.socket.parent / 'ctl.log').stat().st_size for peer in peers]
            host.call('interact', *lever, 'up')
            for peer, offset in zip(peers, after, strict=True):
                check_frame(peer, block, True, refs[kind, 5, 1], after=offset)
            assert host.clock() == clock
            host.step_to(clock + 1)
            after = [(peer.socket.parent / 'ctl.log').stat().st_size for peer in peers]
            guest.call('interact', *lever, 'up')
            for peer, offset in zip(peers, after, strict=True):
                check_frame(peer, block, False, refs[kind, 9, 1], after=offset)
            assert host.clock() == clock + 1
    print(f'Both clients submitted the two {block} shaft halves with Java RPM before and after each lever action.')


def verify_lan_break(args, scratch):
    timing = import_module('test-transmission-timing')
    reference = {int(row[1]): (row[2], int(row[-1])) for row in
                 timing.java_rows('clutch-gearshift-reconnect') if row[0] == '0'}
    pos, gearshift, lever = (8, 102, -10), (9, 102, -10), (8, 104, -10)
    player = 'BreakObserver'
    os.environ['CREATE_SPLIT_SHAFT_RENDER'] = '1'
    (effect,) = timing.break_effects('reconnect', 'clutch')
    cue = effect['sound']
    audio = timing.TEST_AUDIO

    def frames(peer, after):
        log = peer.socket.parent / 'ctl.log'
        return {tuple(line[len(MARKER):].split(',')[:4])
                for line in log.read_bytes()[after:].decode(errors='replace').splitlines()
                if line.startswith(MARKER)}

    def draw_key(at, block):
        return (*map(str, at), f'create:{block}')

    def toggle(peer):
        peer.call('look-at', 8.5, 104.15, -9.5)
        peer.call('interact', *lever, 'up')

    with fixture_world(args, 'ClutchBreakLAN', render=True, pack=args.pack, env=audio) as host:
        host.commands((
            '/fill 4 100 -14 14 100 -5 minecraft:smooth_stone',
            '/fill 4 101 -13 14 106 -6 minecraft:air',
            '/setblock 7 102 -10 create:creative_motor[facing=east]',
            '/data merge block 7 102 -10 {ScrollValue:32}',
            '/setblock 8 102 -10 create:clutch[axis=x,powered=false]',
            '/setblock 8 103 -10 minecraft:stone',
            '/setblock 8 104 -10 minecraft:lever[face=floor,facing=east,powered=false]',
            '/setblock 8 103 -12 minecraft:stone',
            '/setblock 10 103 -10 minecraft:stone',
            '/tp @s 10.5 104 -9.5',
        ))
        for _ in range(4):
            host.step_to(host.clock() + 1)
        start = host.clock()
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(args, scratch, address, player, render=True,
                                       scenario='clutch-conflict-break', pack=args.pack, env=audio) as guest:
            multiplayer.until('guest to enter the conflict world', lambda: any(
                user['name'] == player and user['placed'] for user in host.call('lan', 'status')['guests']
            ))
            host.command(f'/tp {player} 8.5 104 -11.5')
            multiplayer.until('guest to reach the rig', lambda:
                              guest.call('state')['player']['position'] == [8.5, 104, -11.5])
            start_sounds = {peer: peer.call('status')['heard'].get(cue, 0) for peer in (host, guest)}
            for tick in range(1, 10):
                host.step_to(start + tick)
                if tick == 3:
                    toggle(host)
                    host.call('wait', 2)
                    assert host.call('block', *lever)['state'].endswith('powered=true]')
                if tick == 5:
                    host.commands((
                        '/setblock 9 102 -10 create:gearshift[axis=x,powered=false]',
                        '/setblock 10 102 -10 create:creative_motor[facing=west]',
                        '/data merge block 10 102 -10 {ScrollValue:64}',
                    ))
                if tick == 7:
                    for peer in (host, guest):
                        after = (peer.socket.parent / 'ctl.log').stat().st_size
                        peer.call('look-at', 9.0, 102.5, -9.5)
                        multiplayer.until('both transmissions to draw before the break', lambda:
                                          {draw_key(pos, 'clutch'), draw_key(gearshift, 'gearshift')}
                                          <= frames(peer, after))
                if tick == 8:
                    toggle(host)
                if tick in (7, 8, 9):
                    gate, drops = reference[tick]
                    state = ('minecraft:air' if gate == 'missing' else
                             f'create:clutch[axis=x,powered={str(gate == "open").lower()}]')
                    for peer in (host, guest):
                        multiplayer.until(f'both clients to see the Java outcome on tick {tick}', lambda:
                                          peer.call('block', *pos)['state'] == state and
                                          timing.transmission_drops(peer, 'clutch', pos) == drops)
                        expected_sounds = start_sounds[peer] + (gate == 'missing')
                        multiplayer.until(f'both clients to hear the Java break cue on tick {tick}', lambda:
                                          peer.call('status')['heard'].get(cue, 0) == expected_sounds)
                    assert host.clock() == start + tick
            for peer in (host, guest):
                after = (peer.socket.parent / 'ctl.log').stat().st_size
                peer.call('look-at', 9.0, 102.5, -9.5)
                multiplayer.until('the surviving Gearshift to draw', lambda:
                                  draw_key(gearshift, 'gearshift') in frames(peer, after))
                peer.call('wait', 4)
                assert draw_key(pos, 'clutch') not in frames(peer, after)
    print('Host and guest matched the Java Clutch break tick, drop, and sound. Both stopped drawing the Clutch shafts.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--frames", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--lan", action="store_true")
    mode.add_argument("--lan-break", action="store_true")
    mode.add_argument("--axes", action="store_true")
    mode.add_argument("--lan-axes", action="store_true")
    parser.add_argument("--lan-block", choices=("clutch", "gearshift"), default="gearshift")
    args = parser.parse_args()
    if args.lan or args.lan_break or args.lan_axes:
        with TemporaryDirectory(prefix="hc-srl-") as scratch:
            run = verify_axes if args.lan_axes else verify_lan_break if args.lan_break else verify_lan
            run(args, Path(scratch))
    elif args.axes:
        verify_axes(args)
    else:
        verify(args)


if __name__ == "__main__":
    main()
