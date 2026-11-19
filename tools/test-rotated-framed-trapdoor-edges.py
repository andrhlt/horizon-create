#!/usr/bin/env python3
"""Click a mounted trapdoor on a train while it turns through a curve."""
import argparse
import csv
import re
from math import floor
from importlib import import_module
from math import hypot
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

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
        f'/setblock {x} {y} {z - 1} create:framed_glass_trapdoor[facing=east,half=top]',
        f'/setblock {x} {y} {z + 1} create:framed_glass_trapdoor[facing=east,half=top]',
        f'/summon minecraft:marker {x + .5} {y - 1} {z + .5} '
        '{CreateSuperGlue:1b,From:[-0.5d,0d,-1.5d],To:[0.5d,2d,1.5d]}',
    ))


def run(args):
    with TemporaryDirectory(prefix='hc-rotated-door-') as scratch, fixture_world(
        args, 'rotated-framed-trapdoor-edges', train.STRUCTURE, render=True, pack=args.pack, env=mounted.ENV
    ) as host:
        train.setup(host, curve.layout, before_glue=cells)
        host.command('/attribute @s minecraft:gravity base set 0')
        port = host.call('lan', 'open', 0, 'commands', 'force')['port']
        with mp.joined_client(args, Path(scratch), f'127.0.0.1:{port}', GUEST,
                              render=True, scenario='rotated-framed-trapdoor-edges', pack=args.pack, env=mounted.ENV) as guest:
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
                with (ROOT / 'fixtures/rotated-framed-trapdoor-edges-java.csv').open() as f:
                    cases = {(r['open'] == 'true', float(r['x']), float(r['z'])): r['hit'] == 'true'
                             for r in csv.DictReader(f)}
                probes = [(False,.98,.98), (False,-.08,.50), (False,.50,1.08),
                          (True,.02,.02), (True,.02,.98), (True,.50,.50), (True,-.08,.50)]
                failures = []
                for side in (-1, 1):
                    selector = f'@e[type=minecraft:interaction,nbt={{CreateTrainTrapdoorPos:[I;2,2,{side}]}},limit=1]'
                    reply = host.command(f'/data get entity {selector} Pos')
                    coords = re.findall(r'([-+0-9.eE]+)d', reply)
                    if len(coords) != 3:
                        raise RuntimeError(f'Missing framed proxy {side}: {reply}')
                    x, proxy_y, z = map(float, coords)
                    y = proxy_y - .8125
                    index_reply = host.command(f'/data get entity {selector} CreatePartIndex')
                    match = re.search(r'entity data: (\d+)$', index_reply)
                    if not match:
                        raise RuntimeError(f'Missing framed proxy part index: {index_reply}')
                    display = f'@e[type=minecraft:block_display,nbt={{CreatePartIndex:{int(match[1])-1}}},limit=1]' 
                    reply = host.command(f'/data get entity {display} transformation.left_rotation')
                    nums = re.findall(r'([-+0-9.eE]+)f', reply)
                    if len(nums) != 4:
                        raise RuntimeError(f'Could not read framed panel rotation: {reply}')
                    qx, qy, qz, qw = map(float, nums)
                    def point(lx, lz):
                        dx, dz = lx - .5, lz - .5
                        return (x + (1-2*(qy*qy+qz*qz))*dx + 2*(qx*qz+qy*qw)*dz,
                                z + 2*(qx*qz-qy*qw)*dx + (1-2*(qx*qx+qy*qy))*dz)
                    def is_open(which):
                        path = f'CreateTrain.Blocks[{{Pos:[I;2,2,{which}]}}].BlockState.Properties.open'
                        return '"true"' in host.command(f'/data get entity {train.ENTITY} {path}')
                    def click(lx, lz):
                        wx, wz = point(lx, lz)
                        host.command(f'/tp {GUEST} {wx} {y + 1.0} {wz}')
                        guest.call('wait', 4)
                        mounted.mouse_at(guest, (wx, y + .5, wz))
                    def ensure_open(want):
                        if is_open(side) == want:
                            return
                        click(.09375 if is_open(side) else .5, .5)
                        if is_open(side) != want:
                            raise RuntimeError(f'Could not reset framed panel {side}')
                    for was_open, lx, lz in probes:
                        ensure_open(was_open)
                        other = is_open(-side)
                        click(lx, lz)
                        hit = is_open(side) != was_open
                        expected = cases[(was_open,lx,lz)]
                        if hit != expected or is_open(-side) != other:
                            failures.append((side,was_open,lx,lz,expected,hit,other,is_open(-side)))
                if failures:
                    raise AssertionError(f'Rotated framed edge mismatches (side,open,x,z,Java,Horizon,other before/after): {failures}')
                print(f'Guest matched {2 * len(probes)} Java framed-panel edge rays without changing the neighboring panel.')
            finally:
                host.call('key', 'w', 'up')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path)
    run(parser.parse_args())
