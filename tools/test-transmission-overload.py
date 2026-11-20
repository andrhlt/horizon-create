#!/usr/bin/env python3
"""Compare real overload and recovery through a Clutch and Gearshift."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

timing = import_module("test-transmission-timing")
FIELDS = ("rig", "tick", "phase", "powered", "gate_rpm", "gate_effective_rpm",
          "press_rpm", "press_effective_rpm")


def speed(data):
    rpm = timing.rpm(data)
    stress = re.search(r'\bStress: ([\d.]+)', data)
    capacity = re.search(r'\bCapacity: ([\d.]+)', data)
    effective = 0 if stress and capacity and float(stress[1]) > float(capacity[1]) else rpm
    return f"{rpm:.9g}", f"{effective:.9g}"


def verify(args):
    expected = timing.java_rows("clutch-gearshift-overload")
    actual = []
    lanes = (-12, -7)
    with fixture_world(args, "TransmissionOverload", pack=args.pack) as world:
        world.commands((
            '/fill 4 100 -15 14 100 -5 minecraft:smooth_stone',
            '/fill 4 101 -15 14 107 -5 minecraft:air',
            '/tp @s 5.5 101 -9.5',
        ))
        for rig, z in enumerate(lanes):
            clutch = rig == 0
            block = 'clutch' if clutch else 'gearshift'
            if clutch:
                world.command(f'/setblock 8 103 {z} minecraft:redstone_block')
            world.commands((
                f'/setblock 8 102 {z} create:{block}[axis=x,powered={str(clutch).lower()}]',
                f'/setblock 9 102 {z} create:mechanical_press[facing=east]',
                f'/setblock 10 102 {z} create:mechanical_press[facing=east]',
                f'/setblock 7 102 {z} create:hand_crank[facing=west]',
            ))
        for _ in range(4):
            world.step_to(world.clock() + 1)
        start = world.clock()
        for tick in range(14):
            if tick:
                world.step_to(start + tick)
            for rig, z in enumerate(lanes):
                for phase in range(2 if tick in (2, 4, 7) else 1):
                    if phase:
                        if tick == 2:
                            world.command(f'/tp @s 5.5 101 {z + .5}')
                            world.call('wait', 2)
                            world.call('interact', 7, 102, z, 'west')
                        else:
                            powered = (rig != 0) if tick == 4 else (rig == 0)
                            block = "redstone_block" if powered else "air"
                            world.command(f'/setblock 8 103 {z} minecraft:{block}')
                        world.call('wait', 2)
                        assert world.clock() == start + tick, (rig, tick, phase)
                    state = world.call('block', 8, 102, z)['state']
                    gate, press = world.commands(f'/data get block {x} 102 {z}' for x in (8, 9))
                    actual.append([str(rig), str(tick), str(phase), str("powered=true" in state).lower(),
                                   *speed(gate), *speed(press)])
    trace = ROOT / '.local/clutch-gearshift-overload-horizon.csv'
    with trace.open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(FIELDS)
        writer.writerows(actual)
    timing.compare("Clutch and Gearshift under overload", expected, actual)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())
