#!/usr/bin/env python3
"""Walk through paired mounted Train Doors and an obstructed platform exit."""
import argparse
import re
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from fixture_world import fixture_world

pair = import_module('test-paired-train-door')
train = pair.train


def check_position(host, client, who, y, label):
    pose = client.call('state')['player']['position']
    server = host.command(f'/data get entity {who} Pos')
    authoritative = [float(n) for n in re.findall(r'(' + train.NUMBER + r')d', server)]
    print(f'{who}: {label}, client={pose}, server={server}', flush=True)
    assert len(authoritative) == 3, server
    assert all(abs(a-b) < .05 for a,b in zip(pose, authoritative, strict=True)), (pose, authoritative)
    assert abs(pose[1]-y) < .05, pose
    return pose


def walk(client, frames=20):
    client.call('script', script=f'key w down\nwait {frames}\nkey w up\nwait 4\n')


def run_case(args, case):
    # Each physical layout has its own world. Do not teleport players back
    # onto an old tracked carriage after modifying an occupied landing.
    with ExitStack() as stack:
        scenario = f'train-door-passage-{case}' + ('-lan' if args.multiplayer else '')
        host = stack.enter_context(fixture_world(args, scenario, train.STRUCTURE,
            render=True, pack=args.pack, env={'HORIZON_NO_AUDIO': '1'}))
        train.setup(host, before_glue=pair.place_pair, take_controls=False)
        x, y, z = train.X + 3.5, train.Y + 3, train.Z - 1
        host.command(f'/fill {train.X+2} {y-1} {z-5} {train.X+5} {y-1} {z-1} minecraft:smooth_stone')
        if case == 'obstructed':
            host.commands(f'/setblock {train.X+3} {y+dy} {z-1} minecraft:stone' for dy in (0,1))
        riders = [(host, '@s')]
        if args.multiplayer:
            guest = pair.open_guest(host, args, stack, scenario,
                {'HORIZON_NO_AUDIO': '1'}, 'PassageGuest')
            riders.append((guest, 'PassageGuest'))
        paths = [f'CreateTrain.Blocks[{{Pos:[I;{leaf},{h},-1]}}].BlockState.Properties.open'
                 for leaf in (2, 3) for h in (2, 3)]
        assert pair.read_halves(host, paths) == [True]*4
        if case == 'closed':
            # Manually close the initially station-open pair through its left leaf.
            aim = x-.8
            host.commands(('/attribute @s minecraft:gravity base set 0',
                '/item replace entity @s hotbar.0 with minecraft:air',
                f'/tp @s {aim} {y} {z-1.2} 0 20'))
            host.call('key', '1', 'tap')
            host.call('wait', 5)
            host.call('look-at', aim, y+.5, z+.9)
            host.call('mouse', 'right', 'click')
            host.call('wait', 5)
        for _ in range(10):
            host.step_to(host.clock()+1)
        opened = case != 'closed'
        assert pair.read_halves(host, paths) == [opened]*4
        host.command('/tick unfreeze')
        for client, who in riders:
            for _, name in riders:
                if name != who:
                    host.command(f'/tp {name} {x+2} {y} {z-4}')
            host.call('command', f'/gamemode survival {who}')
            host.commands((f'/attribute {who} minecraft:gravity base set 0.08',
                f'/attribute {who} minecraft:movement_speed base set 0.1',
                f'/tp {who} {x} {y+.0001} {z+1.5} 180 0'))
            client.call('wait', 8)
            check_position(host, client, who, y, f'{case} start')
            walk(client)
            pose = check_position(host, client, who, y, case)
            if case == 'closed':
                assert z+1.25 < pose[2] < z+1.35, pose
            elif case == 'obstructed':
                assert z+.25 < pose[2] < z+.35, pose
            else:
                assert pose[2] < z-.4, pose
                # Return from the landing through the open pair using real
                # walking, rather than an artificial teleport onto the deck.
                client.call('look-at', x, y+1.62, z+2)
                walk(client)
                pose = check_position(host, client, who, y, 'reboarded')
                assert z+.4 < pose[2] < z+2, pose
        assert pair.read_halves(host, paths) == [opened]*4


def run(args):
    for case in ('closed', 'open', 'obstructed'):
        run_case(args, case)
    print('Paired train doors blocked closed, passed both ways open, and respected a solid platform obstruction.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    parser.add_argument('--multiplayer', action='store_true')
    run(parser.parse_args())
