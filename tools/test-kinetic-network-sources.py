#!/usr/bin/env python3
"""Check kinetic source conflicts, merges, separation and persistence."""

import argparse
from math import isclose
from pathlib import Path
import re

from fixture_world import fixture_world

LEFT_MOTOR = (1, 100, 1)
LEFT_SHAFTS = ((2, 100, 1), (3, 100, 1))
BRIDGE = (4, 100, 1)
BRIDGE_MIDDLE = (5, 100, 1)
BRIDGE_JOIN = (6, 100, 1)
RIGHT_SHAFT = (7, 100, 1)
RIGHT_MOTOR = (8, 100, 1)


def coords(pos):
    return " ".join(map(str, pos))


def block_data(control, pos):
    return control.command(f"/data get block {coords(pos)}")


def network_values(control, pos):
    data = block_data(control, pos)
    values = []
    for key in ("Speed", "Capacity", "Stress"):
        match = re.search(rf"\b{key}: (-?[\d.]+)f?", data)
        if match is None:
            raise RuntimeError(f"No {key} in kinetic data at {pos}: {data}")
        values.append(float(match[1]))
    return tuple(values)


def expect_network(control, positions, speed, capacity, stress=0.0):
    expected = (speed, capacity, stress)
    for pos in positions:
        actual = network_values(control, pos)
        if any(not isclose(got, want, rel_tol=0.0, abs_tol=0.00001)
               for got, want in zip(actual, expected, strict=True)):
            raise RuntimeError(f"Kinetic state at {pos}: expected {expected}, got {actual}")


def is_air(control, pos):
    control.command(f"/data get block {coords(pos)}")
    block = control.call("block", *pos)
    if block.get("block") != "minecraft:air":
        raise RuntimeError(f"Expected Java's conflicting bridge to break at {pos}, got {block}")


def run(args):
    left = (LEFT_MOTOR, *LEFT_SHAFTS)
    right = (RIGHT_SHAFT, RIGHT_MOTOR)
    with fixture_world(args, "KineticSourceTransitions") as control:
        control.commands((
            "/fill 0 99 0 10 99 2 minecraft:smooth_stone",
            "/fill 0 100 0 10 104 2 minecraft:air",
            f"/setblock {coords(LEFT_MOTOR)} create:creative_motor[facing=east]",
            *(f"/setblock {coords(pos)} create:shaft[axis=x]" for pos in LEFT_SHAFTS),
            f"/setblock {coords(RIGHT_SHAFT)} create:shaft[axis=x]",
            f"/setblock {coords(RIGHT_MOTOR)} create:creative_motor[facing=west]",
        ))
        start = control.clock()
        for tick in range(1, 5):
            control.step_to(start + tick)
        expect_network(control, left, 16.0, 262144.0)
        expect_network(control, right, -16.0, 262144.0)

        control.restart()
        control.step_to(control.clock() + 1)
        expect_network(control, left, 16.0, 262144.0)
        expect_network(control, right, -16.0, 262144.0)

        for pos in (BRIDGE, BRIDGE_MIDDLE):
            control.command(f"/setblock {coords(pos)} create:shaft[axis=x]")
            control.step_to(control.clock() + 1)
        control.command(f"/setblock {coords(BRIDGE_JOIN)} create:shaft[axis=x]")
        control.step_to(control.clock() + 1)
        is_air(control, BRIDGE_JOIN)
        expect_network(control, left, 16.0, 262144.0)
        expect_network(control, right, -16.0, 262144.0)

        control.command(f"/data merge block {coords(RIGHT_MOTOR)} {{ScrollValue:8}}")
        control.step_to(control.clock() + 1)
        control.command(f"/setblock {coords(BRIDGE_JOIN)} create:shaft[axis=x]")
        control.step_to(control.clock() + 1)
        is_air(control, BRIDGE_JOIN)
        expect_network(control, left, 16.0, 262144.0)
        expect_network(control, right, -8.0, 131072.0)

        control.command(f"/data merge block {coords(RIGHT_MOTOR)} {{ScrollValue:-16}}")
        control.step_to(control.clock() + 1)
        expect_network(control, left, 16.0, 262144.0)
        expect_network(control, right, 16.0, 262144.0)

        control.command(f"/setblock {coords(BRIDGE_JOIN)} create:shaft[axis=x]")
        control.step_to(control.clock() + 1)
        merged = (*left, BRIDGE, BRIDGE_MIDDLE, BRIDGE_JOIN, *right)
        expect_network(control, merged, 16.0, 524288.0)

        control.command(f"/data merge block {coords(RIGHT_MOTOR)} {{ScrollValue:-8}}")
        control.step_to(control.clock() + 1)
        expect_network(control, merged, 16.0, 393216.0)
        control.command(f"/data merge block {coords(LEFT_MOTOR)} {{ScrollValue:8}}")
        control.step_to(control.clock() + 1)
        expect_network(control, merged, 8.0, 262144.0)
        control.commands((
            f"/data merge block {coords(LEFT_MOTOR)} {{ScrollValue:16}}",
            f"/data merge block {coords(RIGHT_MOTOR)} {{ScrollValue:-16}}",
        ))
        control.step_to(control.clock() + 1)
        expect_network(control, merged, 16.0, 524288.0)

        control.command(f"/setblock {coords(BRIDGE)} minecraft:air")
        control.step_to(control.clock() + 1)
        expect_network(control, left, 16.0, 262144.0)
        expect_network(control, right, 16.0, 262144.0)

        control.command(f"/data merge block {coords(RIGHT_MOTOR)} {{ScrollValue:32}}")
        control.step_to(control.clock() + 1)
        control.command(f"/setblock {coords(BRIDGE)} create:shaft[axis=x]")
        control.step_to(control.clock() + 1)
        is_air(control, BRIDGE)
        expect_network(control, left, 16.0, 262144.0)
        expect_network(control, right, -32.0, 524288.0)

        control.command(f"/data merge block {coords(RIGHT_MOTOR)} {{ScrollValue:-16}}")
        control.step_to(control.clock() + 1)
        control.command(f"/setblock {coords(BRIDGE)} create:shaft[axis=x]")
        control.step_to(control.clock() + 1)
        expect_network(control, merged, 16.0, 524288.0)

        control.restart()
        control.step_to(control.clock() + 1)
        expect_network(control, merged, 16.0, 524288.0)

    print("Kinetic equal/weaker/stronger source conflicts, equal/unequal merges, split, idle reopen and active reopen passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())


if __name__ == "__main__":
    main()
