#!/usr/bin/env python3
"""Compare paired sliding/folding doors under mixed power and support removal."""
import argparse
import csv
from collections import Counter
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

pairs = import_module('test-world-paired-doors')
nozzle = pairs.nozzle
MATERIALS = ('brass_door', 'copper_door')


def sample(world, positions, material):
    values = [[], [], []]
    for pos in positions:
        state = nozzle.state(world, pos)
        if not state.startswith(f'create:{material}['):
            for row in values:
                row.append('-')
            continue
        for row, key in zip(values, pairs.PROPERTIES, strict=True):
            row.append('1' if f'{key}=true' in state else '0')
    return tuple(''.join(row) for row in values)


def verify_cues(world, listeners, start, positions, expected):
    def position(row):
        return tuple(value + .5 for value in positions[int(row['half'])])

    def compare(actual, authority):
        wanted = Counter((row['sound'], position(row), float(row['volume']),
                          int(row['tick']) if authority else None) for row in expected)
        for row in actual:
            if authority:
                tick, sound, *values = row
            else:
                sound, category, *values = row
                assert category == '4', row
            x, y, z, volume, pitch = map(float, values)
            key = (sound, (x, y, z), volume, int(tick) - start if authority else None)
            assert wanted[key] > 0, (row, wanted)
            wanted[key] -= 1
            assert (.9 <= pitch <= 1.0) if volume == 1.0 else pitch == 1.0, row
        assert not +wanted, wanted

    compare(pairs.cues(world, 'CREATE_ELEVATOR_SOUND '), True)
    for listener in dict.fromkeys(listeners):
        pairs.multiplayer.until('door sounds to reach the listener', lambda:
                                len(pairs.cues(listener, 'CREATE_ELEVATOR_PLAYBACK ')) >= len(expected))
        compare(pairs.cues(listener, 'CREATE_ELEVATOR_PLAYBACK '), False)


def run(args):
    with (ROOT / 'fixtures/world-paired-doors-power-java.csv').open(newline='') as source:
        rows = list(csv.DictReader(source))
    with (ROOT / 'fixtures/world-paired-doors-power-sound-java.csv').open(newline='') as source:
        sounds = list(csv.DictReader(source))
    assert len(rows) == 64 and len(sounds) == 8
    for material in MATERIALS:
        reference = [row for row in rows if row['material'] == material]
        with ExitStack() as stack:
            world = stack.enter_context(fixture_world(
                args, f'WorldDoorPower{material}{"Lan" if args.lan else "Solo"}',
                render=True, pack=args.pack, env=pairs.ENV))
            positions = pairs.place_pair(world, material, 8, 170, 8)
            actor = pairs.join(args, world, stack, material, pairs.ENV) if args.lan else world
            world.command('/tp @s 10.5 170 10.5')
            if actor is not world:
                world.command(f'/tp {pairs.GUEST} 7.5 170 10.5')
                pairs.multiplayer.until('guest listener to reach the doors', lambda:
                                        actor.call('state')['player']['position'] == [7.5, 170.0, 10.5])
            world.call('wait', 4)
            start = world.clock()
            for offset, row in enumerate(reference):
                assert int(row['tick']) == offset
                if offset:
                    world.step_to(start + offset)
                actions = {
                    3: '/setblock 7 170 8 minecraft:redstone_block',
                    9: '/setblock 10 170 8 minecraft:redstone_block',
                    15: '/setblock 7 170 8 minecraft:air',
                    21: '/setblock 10 170 8 minecraft:air',
                    27: '/setblock 8 169 8 minecraft:air',
                }
                if offset in actions:
                    actor.call("command", actions[offset])
                    if actor is not world:
                        _, x, y, z, block = actions[offset].split()
                        pairs.multiplayer.until('guest block update to reach the server', lambda:
                            'Test passed' in world.command(f'/execute if block {x} {y} {z} {block}'))
                expected = tuple(row[key] for key in pairs.PROPERTIES)
                tests = []
                for index, pos in enumerate(positions):
                    properties = ','.join(
                        f'{key}={"true" if row[key][index] == "1" else "false"}'
                        for key in pairs.PROPERTIES
                    )
                    tests.append(f'/execute if block {nozzle.xyz(pos)} create:{material}[{properties}]')
                authority = world.commands(tests)
                assert all('Test passed' in result for result in authority), (row, authority)
                for viewer in dict.fromkeys((world, actor)):
                    pairs.multiplayer.until(f'client to see door state at tick {offset}', lambda:
                                            sample(viewer, positions, material) == expected)
                print(f'{material},{offset},{",".join(expected)}', flush=True)
                if offset >= 27:
                    assert world.call('block', 8, 169, 8)['block'] == 'minecraft:air'
            verify_cues(world, (world, actor), start, positions,
                        [row for row in sounds if row['material'] == material])
    print('Both paired materials matched all 64 Java power/support states and eight cues.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        p.add_argument(key, type=Path)
    p.add_argument('--pack', type=Path)
    p.add_argument('--lan', action='store_true')
    run(p.parse_args())
