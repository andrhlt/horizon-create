#!/usr/bin/env python3
"""Click a mounted trapdoor on a train while it turns through a curve."""
import argparse
from importlib import import_module
from math import hypot
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import fixture_world

curve = import_module('test-curved-train')
train = curve.train
moving = import_module('test-moving-train-trapdoor')
mounted, mp = moving.mounted, moving.mp
X, Y, Z = curve.X, curve.Y, curve.Z
GUEST = 'RotatedDoorGuest'


def cells(world):
    x, y, z = X + 3, Y + 3, Z
    world.commands((
        f'/setblock {x} {y} {z} minecraft:chest',
        f'/setblock {x} {y} {z - 1} create:train_trapdoor[facing=north,half=bottom]',
        f'/summon minecraft:marker {x + .5} {y - 1} {z + .5} '
        '{CreateSuperGlue:1b,From:[-0.5d,0d,-1.5d],To:[0.5d,2d,0.5d]}',
    ))


def run(args):
    with TemporaryDirectory(prefix='hc-rotated-door-') as scratch, fixture_world(
        args, 'rotated-train-trapdoor', train.STRUCTURE, render=True, pack=args.pack, env=mounted.ENV
    ) as host:
        train.setup(host, curve.layout, before_glue=cells)
        host.command('/attribute @s minecraft:gravity base set 0')
        port = host.call('lan', 'open', 0, 'commands', 'force')['port']
        with mp.joined_client(args, Path(scratch), f'127.0.0.1:{port}', GUEST,
                              render=True, scenario='rotated-train-trapdoor', pack=args.pack, env=mounted.ENV) as guest:
            mp.until('guest to join', lambda: any(g['name'] == GUEST and g['placed']
                                                   for g in host.call('lan', 'status')['guests']))
            host.commands((f'/gamemode survival {GUEST}', f'/attribute {GUEST} minecraft:gravity base set 0',
                           f'/item replace entity {GUEST} hotbar.0 with minecraft:air'))
            guest.call('key', '1', 'tap')
            host.call('key', 'w', 'down')
            try:
                for tick in range(100):
                    host.step_to(host.clock() + 1)
                    values = curve.sample(host)
                    px, pz = X + (values[1] + values[4]) / 2, Z + (values[3] + values[6]) / 2
                    hx = (values[7] + values[10]) / 2 - (values[1] + values[4]) / 2
                    hz = (values[9] + values[12]) / 2 - (values[3] + values[6]) / 2
                    magnitude = hypot(hx, hz)
                    if magnitude and abs(hz / magnitude) > .6 and abs(values[0]) > .05:
                        break
                    if tick % 3 == 2:
                        host.command(f'/tp @s {px:.6f} {Y + 4} {pz + 1.5:.6f}')
                        host.call('wait', 3)
                else:
                    raise AssertionError('Train did not rotate through the curve')
                x, y, z = moving.proxy_pos(host)
                host.command(f'/tp {GUEST} {x + 1.1} {y + 1.0} {z}')
                guest.call('wait', 6)
                before = mounted.heard(guest)
                mounted.mouse_at(guest, (x, y + .09, z))
                path = 'CreateTrain.Blocks[{Pos:[I;2,2,-1]}].BlockState.Properties'
                actual = host.command(f'/data get entity {train.ENTITY} {path}')
                if not all(field in actual for field in ('open: "true"', 'facing: "north"', 'half: "bottom"')):
                    raise AssertionError(f'Rotated trapdoor did not match Java open state: {actual}')
                guest.call('wait', 5)
                if mounted.heard(guest)[len(before):] != ['open']:
                    raise AssertionError('Rotated trapdoor did not produce the Java opening cue')
                print(f'Guest opened the curved train trapdoor at heading component {hz / magnitude:.3f}.')
            finally:
                host.call('key', 'w', 'up')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    run(parser.parse_args())
