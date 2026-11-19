#!/usr/bin/env python3
"""Compare initialized Gearshift redstone changes with unequal live drive speeds."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

timing = import_module("test-transmission-timing")
coords = timing.coordinates
offset_axis = timing.offset_axis
FORWARD = ("east", "up", "south")
BACKWARD = ("west", "down", "north")
FIELDS = ("lane", "axis", "tick", "phase", "powered", "source", "gearshift_rpm",
          "left_motor", "left_rpm", "right_motor", "right_rpm")


def verify(args):
    expected = timing.java_rows("initialized-gearshift")
    observed = []
    rigs = [(lane, axis, (8 + 5 * axis, 105, -12 + 5 * lane))
            for lane in range(2) for axis in range(3)]
    with fixture_world(args, "InitializedGearshift", pack=args.pack) as world:
        world.commands((
            '/fill 5 101 -16 21 101 -4 minecraft:smooth_stone',
            '/fill 5 102 -16 21 109 -4 minecraft:air',
            '/tp @s 13.5 102 -9.5',
        ))
        for lane, axis, pos in rigs:
            left = coords(offset_axis(pos, axis, -1))
            if lane:
                signal = offset_axis(pos, 2, -1) if axis == 0 else offset_axis(pos, 0, 1)
                world.command(f'/setblock {coords(signal)} minecraft:redstone_block')
            world.commands((
                f'/setblock {coords(pos)} create:gearshift[axis={"xyz"[axis]},powered={str(bool(lane)).lower()}]',
                f'/setblock {left} create:creative_motor[facing={FORWARD[axis]}]',
                f'/data merge block {left} {{ScrollValue:32}}',
            ))
        for _ in range(4):
            world.step_to(world.clock() + 1)
        start = world.clock()
        for tick in range(13):
            if tick:
                world.step_to(start + tick)
            for lane, axis, pos in rigs:
                left = offset_axis(pos, axis, -1)
                right = offset_axis(pos, axis, 1)
                if tick == 3:
                    right_speed = 64 if lane else -64
                    world.commands((
                        f'/setblock {coords(right)} create:creative_motor[facing={BACKWARD[axis]}]',
                        f'/data merge block {coords(right)} {{ScrollValue:{right_speed}}}',
                    ))
                for phase in range(2 if tick in (7, 10) else 1):
                    if phase:
                        signal = offset_axis(pos, 2, -1) if axis == 0 else offset_axis(pos, 0, 1)
                        on = lane == 0 if tick == 7 else lane != 0
                        world.command(f'/setblock {coords(signal)} minecraft:{"redstone_block" if on else "air"}')
                        world.call('wait', 2)
                        assert world.clock() == start + tick, (lane, axis, tick)
                    gate = world.call('block', *pos)
                    power = ('missing' if gate['block'] == 'minecraft:air'
                             else str('powered=true' in gate['state']).lower())
                    gate_data, left_data, right_data = world.commands(
                        f'/data get block {coords(at)}' for at in (pos, left, right)
                    )
                    source = re.search(r'\bShaftInputSide: (-?\d+)', gate_data)
                    side = int(source[1]) if source else 0
                    facing = FORWARD[axis] if side > 0 else BACKWARD[axis] if side < 0 else "-"
                    entry = [str(lane), "xyz"[axis], str(tick), str(phase), power, facing,
                             f'{timing.rpm(gate_data):.9g}']
                    for motor in (left_data, right_data):
                        entry.extend((str('id: "create:motor"' in motor).lower(), f'{timing.rpm(motor):.9g}'))
                    observed.append(entry)
    trace = ROOT / '.local/initialized-gearshift-horizon.csv'
    with trace.open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(FIELDS)
        writer.writerows(observed)
    timing.compare("Initialized Gearshift reversals with two live motors", expected, observed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())
