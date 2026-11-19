#!/usr/bin/env python3
"""Compare rapid manual reversal of paired sliding and folding doors with Java."""
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
    with (ROOT / 'fixtures/world-door-rapid-java.csv').open(newline='') as source:
        rows = list(csv.DictReader(source))
    with (ROOT / 'fixtures/world-door-rapid-sound-java.csv').open(newline='') as source:
        sounds = list(csv.DictReader(source))
    with (ROOT / 'fixtures/world-door-rapid-progress-java.csv').open(newline='') as source:
        progress = list(csv.DictReader(source))
    assert len(rows) == 64
    for material in MATERIALS:
        reference = [row for row in rows if row['material'] == material]
        with ExitStack() as stack:
            env = pairs.ENV | {"HORIZON_CREATE_WORLD_DOOR_TRACE": "1"}
            world = stack.enter_context(fixture_world(
                args, f'WorldDoorRapid{material}{"Lan" if args.lan else "Solo"}',
                render=True, pack=args.pack, env=env))
            positions = pairs.place_pair(world, material, 8, 170, 8)
            actor = pairs.join(args, world, stack, material, env) if args.lan else world
            world.command('/tp @s 10.5 170 10.5')
            world.call('look-at', 9, 171, 8.8)
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
                if offset in (3, 6, 9, 18):
                    pairs.click(world, actor, positions[0], closing=offset in (6, 18))
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
                if 3 <= offset < 25:
                    for viewer in dict.fromkeys((world, actor)):
                        pairs.multiplayer.until("both leaves rendered at tick", lambda:
                            all((offset, leaf) in pairs.drawn_samples(viewer, material, start) for leaf in (0, 1)))
                print(f'{material},{offset},{",".join(expected)}', flush=True)
            for viewer in dict.fromkeys((world, actor)):
                reference_progress = [r for r in progress if r["material"] == material]
                actual = pairs.drawn_samples(viewer, material, start)
                for r in reference_progress:
                    key = int(r["tick"]), int(r["leaf"])
                    if not 3 <= key[0] < 25: continue
                    exp = float(r["previous"]), float(r["current"])
                    got = actual.get(key)
                    assert got is not None and all(abs(a-b) < 1e-6 for a,b in zip(got, exp)), (material, key, got, exp)
            verify_cues(world, (world, actor), start, positions,
                        [row for row in sounds if row['material'] == material])
    print('Both materials matched rapid Java states, animation, and cues.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('ctl', 'client', 'resources'):
        p.add_argument(key, type=Path)
    p.add_argument('--pack', type=Path)
    p.add_argument('--lan', action='store_true')
    run(p.parse_args())
