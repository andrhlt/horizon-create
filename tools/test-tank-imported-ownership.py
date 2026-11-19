#!/usr/bin/env python3
"""Check Java-format tank ownership survives import and a cold world reopen."""
import argparse
import json
from pathlib import Path
from fixture_world import ROOT, fixture_world


def probe(world):
    positions = [[9, y, 20] for y in range(170, 174)]
    request = {'op': 'probe', 'positions': positions}
    rows = world.call('create-test-tank-script', json.dumps(request, separators=(',', ':')))['rows']
    for index, row in enumerate(rows):
        expected_root = [9, 170 if index < 2 else 172, 20]
        assert (row['controller'], row['capacity'], row['fluid'], row['amount']) == (
            expected_root, 16000, 'minecraft:water', 4000), row


def loaded(world, x):
    reply = world.call('command', f'/execute if loaded {x} 170 20 run say loaded')
    return bool(reply['chat'])


def probe_cross_chunk(world):
    positions = [[x, 170, z] for x in (15, 16) for z in (20, 21)]
    request = {'op': 'probe', 'positions': positions}
    rows = world.call('create-test-tank-script', json.dumps(request, separators=(',', ':')))['rows']
    for row in rows:
        assert (row['controller'], row['capacity'], row['fluid'], row['amount']) == (
            [15, 170, 20], 32000, 'minecraft:water', 12000), row


def step(world, count=3):
    for _ in range(count):
        world.step_to(world.clock() + 1)


def run(args):
    with fixture_world(args, 'TankImportedOwnership', render=False, pack=args.pack,
                       env={'HORIZON_NO_AUDIO': '1', 'CREATE_TANK_SCRIPT_CONTROL': '1'}) as world:
        for y in range(170, 174):
            world.command(f'/setblock 9 {y} 20 create:fluid_tank')
        for _ in range(3):
            world.step_to(world.clock() + 1)
        for y in range(170, 174):
            world.command(f'/data remove block 9 {y} 20 CreateTankController')
            world.command(f'/data remove block 9 {y} 20 LastKnownPos')
            world.command(f'/data merge block 9 {y} 20 {{LastKnownPos:{{X:9,Y:{y},Z:20}}}}')
        for y in (170, 172):
            world.command(f'/data merge block 9 {y} 20 {{Size:1,Height:2,TankContent:{{Fluid:{{id:"minecraft:water",amount:4000}}}}}}')
        for y in (171, 173):
            world.command(f'/data merge block 9 {y} 20 {{Controller:{{X:9,Y:{y-1},Z:20}}}}')
        probe(world)
        for x in (15, 16):
            for z in (20, 21):
                world.command(f'/setblock {x} 170 {z} create:fluid_tank')
        step(world)
        world.command('/data merge block 15 170 20 {TankContent:{Fluid:{id:"minecraft:water",amount:12000}}}')
        probe_cross_chunk(world)
        world.restart()
        probe(world)
        for _ in range(3):
            world.step_to(world.clock() + 1)
            probe(world)
        probe_cross_chunk(world)
        # At x=80, the controller's chunk is actually unloaded while the
        # other half of the tank remains loaded at the render-distance edge.
        world.command('/tp @s 80 170 20')
        step(world)
        assert not loaded(world, 15) and loaded(world, 16), 'expected only the member chunk loaded'
        world.command('/tp @s 96 170 20')
        step(world)
        assert not loaded(world, 15) and not loaded(world, 16), 'expected both tank chunks unloaded'
        world.command('/tp @s 9 170 20')
        step(world)
        assert loaded(world, 15) and loaded(world, 16), 'expected both tank chunks reloaded'
        probe(world)
        probe_cross_chunk(world)
    print('Imported ownership and a cross-chunk tank survived cold reopen, partial unload, and full reload.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ctl', 'client', 'resources'):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument('--pack', type=Path, default=ROOT / '.local/create.hmod')
    run(parser.parse_args())
