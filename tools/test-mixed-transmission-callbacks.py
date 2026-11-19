#!/usr/bin/env python3
"""Replay same-tick redstone changes on a Clutch and Gearshift in series."""

import argparse
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

timing = import_module("test-transmission-timing")
RIGS = ((104, -12), (104, -7), (108, -12), (108, -7))
FIELDS = ("rig", "tick", "phase", "left_powered", "right_powered",
          "left_rpm", "middle_rpm", "right_rpm", "output_rpm")


def verify(args):
    fixture = 'clutch-gearshift-mixed-bend' if args.bend else 'clutch-gearshift-mixed-callbacks'
    expected = timing.java_rows(fixture)
    actual = []
    xyz = timing.coordinates
    rigs = []
    name = 'MixedTransmissionBend' if args.bend else 'MixedTransmissionCallbacks'
    with fixture_world(args, name, pack=args.pack) as world:
        world.commands((
            '/fill 4 100 -15 14 100 -5 minecraft:smooth_stone',
            '/fill 4 101 -15 14 112 -5 minecraft:air',
            '/tp @s 11.5 101 -9.5',
        ))
        for rig, (y, z) in enumerate(RIGS):
            left, right = ("clutch", "gearshift") if rig < 2 else ("gearshift", "clutch")
            first = (8, y, z)
            second = (9, y + 1, z) if args.bend else (10, y, z)
            output = (9, y + 2, z) if args.bend else (11, y, z)
            signals = ((8, y, z - 1), (9, y + 1, z + 1)) if args.bend else ((8, y + 1, z), (10, y + 1, z))
            middle = 'gearbox[axis=z]' if args.bend else 'shaft[axis=x]'
            second_axis = 'y' if args.bend else 'x'
            rigs.append((first, (9, y, z), second, output, signals, left, right))
            world.commands((
                f'/setblock 7 {y} {z} create:creative_motor[facing=east]',
                f'/setblock {xyz(first)} create:{left}[axis=x,powered=false]',
                f'/setblock 9 {y} {z} create:{middle}',
                f'/setblock {xyz(second)} create:{right}[axis={second_axis},powered=false]',
                f'/setblock {xyz(output)} create:shaft[axis={second_axis}]',
                f'/data merge block 7 {y} {z} {{ScrollValue:32}}',
            ))
        for _ in range(4):
            world.step_to(world.clock() + 1)
        start = world.clock()
        for tick in range(11):
            if tick:
                world.step_to(start + tick)
            for rig, (first, middle, second, output, signals, left, right) in enumerate(rigs):
                order = signals if rig % 2 == 0 else signals[::-1]
                for phase in range(3 if tick in (3, 6) else 1):
                    if phase:
                        signal = "redstone_block" if tick == 3 else "air"
                        world.command(f'/setblock {xyz(order[phase - 1])} minecraft:{signal}')
                        world.call('wait', 2)
                        assert world.clock() == start + tick, (rig, tick, phase)
                    states = [world.call('block', *pos) for pos in (first, second)]
                    blocks = (f'create:{left}', f'create:{right}')
                    assert tuple(state["block"] for state in states) == blocks, (rig, tick, phase, states)
                    power = [str("powered=true" in state["state"]).lower() for state in states]
                    values = world.commands(f'/data get block {xyz(pos)}' for pos in (first, middle, second, output))
                    actual.append([str(rig), str(tick), str(phase), *power,
                                   *(f"{timing.rpm(data):.9g}" for data in values)])
    trace = ROOT / f'.local/{fixture}-horizon.csv'
    with trace.open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(FIELDS)
        writer.writerows(actual)
    timing.compare('Mixed transmission callbacks through a Gearbox' if args.bend else
                   'Mixed transmission callbacks on the same tick', expected, actual)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument('--bend', action='store_true')
    verify(parser.parse_args())
