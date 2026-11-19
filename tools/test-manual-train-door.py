#!/usr/bin/env python3
"""Use a mounted Train Door and compare both halves with Java."""
import argparse
import csv
from contextlib import ExitStack
from tempfile import TemporaryDirectory
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT, fixture_world

doors = import_module('test-scheduled-train-doors')
train = doors.train


def run(args):
    with (ROOT / 'fixtures/manual-train-door-java.csv').open() as f:
        rows = list(csv.DictReader(f))
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, 'manual-train-door', train.STRUCTURE, render=True, pack=args.pack,
                       env={'HORIZON_NO_AUDIO':'1'}))
        train.setup(world, before_glue=doors.place_doors, take_controls=False)
        actor, who = world, '@s'
        if args.multiplayer:
            who = 'ManualDoorGuest'
            port = world.call('lan', 'open', 0, 'commands', 'force')['port']
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix='hc-manual-door-guest-')))
            actor = stack.enter_context(doors.conductor.multiplayer.joined_client(
                args, scratch, f'127.0.0.1:{port}', who, render=True,
                scenario='manual-train-door', pack=args.pack, env={'HORIZON_NO_AUDIO':'1'}))
            doors.conductor.multiplayer.until('the door guest to join', lambda: any(
                link['name'] == who and link['placed'] for link in world.call('lan', 'status')['guests']))
        world.commands((f'/attribute {who} minecraft:gravity base set 0',
                        f'/item replace entity {who} hotbar.0 with minecraft:air'))
        actor.call('key', '1', 'tap')
        x, y, z = train.X + 4, train.Y + 3, train.Z - 1
        paths = [f'CreateTrain.Blocks[{{Pos:[I;3,{h},-1]}}].BlockState.Properties.open' for h in (2,3)]
        errors = []
        for row in rows:
            if row['action'] in ('closed', 'opened'):
                # Open north/left panels slide toward the adjacent block; a
                # closed panel occupies its original block's north-facing plane.
                aim_x = x - .3 if row['action'] == 'closed' else x + .5
                world.command(f'/tp {who} {aim_x} {y} {z - 1.2} 0 20')
                world.call('wait', 5)
                actor.call('look-at', aim_x, y + .5, z + .9)
                actor.call('mouse', 'right', 'click')
                world.call('wait', 4)
            elif row['action'].endswith('_next_tick'):
                world.step_to(world.clock() + 1)
            result = world.commands(f'/data get entity {train.ENTITY} {path}' for path in paths)
            actual = [value.endswith('"true"') for value in result]
            expected = [row['lower_open'] == 'true', row['upper_open'] == 'true']
            if actual != expected:
                errors.append((row['action'], expected, actual))
        if errors:
            raise AssertionError(f'Manual mounted train door: {errors}')
    print('Manual mounted Train Door and next-tick persistence matched Java.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    parser.add_argument('--multiplayer', action='store_true')
    run(parser.parse_args())
