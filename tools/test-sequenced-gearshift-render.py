#!/usr/bin/env python3
"""Run the actual Sequenced Gearshift program and compare two rotating inserts."""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from math import fmod, isclose
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from fixture_world import ROOT, fixture_world

MARKER = 'CREATE_SPLIT_SHAFT_FRAME '


def load_test(name):
    spec = spec_from_file_location(name, ROOT / 'tools' / f'{name}.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_java():
    result = ({}, {})
    with (ROOT / "fixtures/sequenced-gearshift-render-java.csv").open(newline="") as source:
        for row in csv.DictReader(source):
            result[int(row["axis"])][int(row["tick"])] = (
                float(row["java_phase"]), float(row["negative_rpm"]), float(row["positive_rpm"]),
            )
    return result


def frame(log, pos, clock, axis, speeds, *, after=0):
    boundary = monotonic() + 3
    phase = 22.5 if (pos[(axis + 1) % 3] + pos[(axis + 2) % 3]) % 2 == 0 else 0.0
    last = None
    while monotonic() < boundary:
        for line in reversed(log.read_bytes()[after:].decode(errors="replace").splitlines()):
            if not line.startswith(MARKER):
                continue
            row = line[len(MARKER):].split(',')
            if len(row) != 16:
                continue
            x, y, z, kind, observed_axis, _, source, tick, partial, offset, neg, positive, angle_neg, angle_pos, vneg, vpos = row
            if tuple(map(int, (x, y, z))) != pos or (clock is not None and int(tick) != clock):
                continue
            last = row
            if (float(neg), float(positive)) != speeds:
                continue
            if kind != 'create:sequenced_gearshift' or int(observed_axis) != axis or float(offset) != phase:
                raise RuntimeError(f'Unexpected Sequenced Gearshift orientation or phase: {row}.')
            if min(int(vneg), int(vpos)) <= 0 or (speeds[0] != speeds[1] and source != '-1'):
                raise RuntimeError(f'Missing original shaft-half vertices or invalid input side: {row}.')
            time = int(tick) + float(partial)
            for expected_rpm, angle in zip(speeds, (angle_neg, angle_pos), strict=True):
                expected = fmod(time * expected_rpm * 3 / 10, 360) + phase
                error = (float(angle) - expected + 180) % 360 - 180
                if not isclose(error, 0.0, abs_tol=0.0002):
                    raise RuntimeError(f'Incorrect shaft angle {angle}, expected {expected} in {row}.')
            return float(partial)
        sleep(0.05)
    raise RuntimeError(f'Expected both Java Sequenced Gearshift shaft halves at {pos}, tick {clock}, RPM {speeds}. Last matching frame {last}.')


def verify(args):
    editor=load_test('test-sequenced-gearshift-editor')
    horizontal, vertical = read_java()
    assert len(horizontal) == 44 and len(vertical) == 44, (len(horizontal), len(vertical))
    pos=(12,103,-12 if vertical[0][0] == 22.5 else -11)
    x,y,z=pos
    with fixture_world(args, 'SequencedSplitShaftRender', render=True, pack=args.pack,
                       env={'CREATE_SPLIT_SHAFT_RENDER': '1'}) as control:
        editor.setup(control)
        control.commands((
            '/setblock 8 101 -11 minecraft:comparator[facing=south]',
            f'/setblock {x} {y-1} {z} create:creative_motor[facing=up]',
            f'/setblock {x} {y} {z} create:sequenced_gearshift[axis=x,state=0,vertical=true]',
            f'/setblock {x} {y+1} {z} create:shaft[axis=y]',
        ))
        start=control.clock()
        partials=set()
        for tick in range(44):
            if tick:
                control.step_to(start+tick)
            if tick == 2:
                editor.configure(control)
                editor.wait_until(control, 'the original program to save', lambda: editor.program_matches(control, editor.original_program()))
            if tick == 39:
                editor.open_editor(control)
                control.call('click-at', *editor.widget(control, 'Confirm'))
                editor.wait_until(control, 'the active turn to cancel', lambda: editor.sample(
                    control.command(f'/data get block {editor.coords(editor.SEQUENCER)}'), 'InstructionIndex',
                ) == -1)
            for axis, target, info in ((0,editor.SEQUENCER,horizontal[tick]),(1,pos,vertical[tick])):
                control.call('look-at', *(value + 0.5 for value in target))
                partials.add(frame(control.socket.parent/'ctl.log', target, start+tick, axis, info[1:]))
            if tick == 0:
                control.commands((
                    '/data merge block 7 101 -10 {ScrollValue:32}',
                    f'/data merge block {x} {y-1} {z} {{ScrollValue:32}}',
                ))
            if tick in (4, 20, 37):
                control.command('/setblock 8 102 -10 minecraft:redstone_block')
            if tick in (5, 21, 40):
                control.command('/setblock 8 102 -10 minecraft:air')
            if tick == 4:
                control.command(f'/setblock {x} {y} {z-1} minecraft:redstone_block')
            if tick == 5:
                control.command(f'/setblock {x} {y} {z-1} minecraft:air')
    if len(partials) < 2:
        raise RuntimeError(f'Expected several animation fractions, found {partials}.')
    print(f'Both horizontal and vertical Sequenced Gearshift insert pairs matched all 88 Java tick states and {len(partials)} submitted render fractions.')


def snapshots(host, guest):
    return tuple((peer.socket.parent / 'ctl.log').stat().st_size for peer in (host, guest))


def verify_lan(args, scratch):
    guest_name = "SeqRender"
    guest_position = (8.5, 101.0, -6.5)
    editor = load_test('test-sequenced-gearshift-editor')
    multiplayer = load_test('test-multiplayer')
    os.environ['CREATE_SPLIT_SHAFT_RENDER'] = '1'
    with fixture_world(args, 'SequencedShaftRenderLAN', render=True, pack=args.pack) as host:
        editor.setup(host)
        host.commands((
            '/data merge block 7 101 -10 {ScrollValue:32}',
            '/tp @s 13.5 101 -7.5',
        ))
        host.step_to(host.clock() + 1)
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(args, scratch, address, guest_name, render=True,
                                       scenario='sequenced-shaft-render', pack=args.pack) as guest:
            multiplayer.until('guest to enter the driven world', lambda: any(
                user['name'] == guest_name and user['placed'] for user in host.call('lan', 'status')['guests']
            ))
            host.commands((f'/gamemode survival {guest_name}', f'/tp {guest_name} 8.5 101 -6.5'))
            multiplayer.until('the guest to reach the sequence editor', lambda: (
                tuple(guest.call('state')['player']['position']) == guest_position
                and guest.call('block', *editor.SEQUENCER)['block'] == 'create:sequenced_gearshift'
            ))
            editor.configure(guest)
            multiplayer.until('server to receive program', lambda: editor.program_matches(host, editor.original_program()))
            after = snapshots(host, guest)
            host.command('/setblock 8 102 -10 minecraft:redstone_block')
            first = host.clock() + 1
            host.step_to(first)
            for peer, offset in zip((host, guest), after, strict=True):
                peer.call('look-at', 8.5, 101.5, -9.5)
                frame(peer.socket.parent/'ctl.log', editor.SEQUENCER, None, 0, (32.0, 64.0), after=offset)
            host.step_to(first + 1)
            editor.open_editor(guest)
            after = snapshots(host, guest)
            guest.call('click-at', *editor.widget(guest, 'Confirm'))
            multiplayer.until('the server to stop the turn', lambda: editor.sample(
                host.command(f'/data get block {editor.coords(editor.SEQUENCER)}'), 'InstructionIndex'
            ) == -1)
            for peer, offset in zip((host, guest), after, strict=True):
                peer.call('look-at', 8.5, 101.5, -9.5)
                frame(peer.socket.parent/'ctl.log', editor.SEQUENCER, None, 0, (32.0, 0.0), after=offset)
            assert host.clock() == first + 1
    print('Both renderers animated the guest-programmed +64 RPM output and stopped it on the guest’s save tick.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-ssr-") as scratch:
            verify_lan(args, Path(scratch))
    else:
        verify(args)


if __name__ == "__main__":
    main()
