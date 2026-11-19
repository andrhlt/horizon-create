#!/usr/bin/env python3
"""Compare Valve power on the release action and every tick through cessation."""
import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from fixture_world import ROOT, fixture_world

spec = spec_from_file_location("valve_fixture", ROOT / "tools/test-copper-valve-handle.py")
valve = module_from_spec(spec)
spec.loader.exec_module(valve)
CASES = (
    ((8, 101, -10), "east", -1, -137, False),
    ((8, 101, -17), "west", 1, 95, True),
)


def measure(control, positions):
    handle, shaft, large, small = control.commands(
        f"/data get block {valve.coord(pos)}" for pos in positions
    )
    return (
        valve.tag(handle, "InUse"), valve.tag(handle, "Cooldown"),
        *(valve.tag(nbt, "Speed") for nbt in (handle, shaft, large, small)),
        valve.tag(handle, "Capacity"),
    )


def press(control, pos, face, rear, sneak):
    x, y, z = pos
    control.command(f"/tp @s {x + 0.5 - 3 * rear} {y}.000 {z + 0.5}")
    control.call("wait", 2)
    if sneak:
        control.call("key", "shift", "down")
        control.call("wait", 2)
    try:
        valve.point_at(control, pos, face)
        control.call("script", script="mouse right down\nwait 2\nmouse right up\nwait 3\n")
    finally:
        if sneak:
            control.call("key", "shift", "up")


def compare(args):
    with (ROOT / "fixtures/valve-action-ticks-java.csv").open() as source:
        _, *rows = csv.reader(source)
    if len(rows) != 48:
        raise RuntimeError(f"Expected 48 Java Valve world samples, got {len(rows)}.")
    commands = [
        "/fill 2 100 -20 15 100 -5 minecraft:smooth_stone",
        "/fill 4 101 -19 13 105 -7 minecraft:air",
        "/gamemode survival",
    ]
    assemblies = []
    for pos, face, rear, _, _ in CASES:
        x, y, z = pos
        assembly = (pos, (x + rear, y, z), (x + 2 * rear, y, z), (x + 2 * rear, y + 1, z + 1))
        assemblies.append(assembly)
        names = (
            f"copper_valve_handle[facing={face},waterlogged=true]",
            "shaft[axis=x]", "large_cogwheel[axis=x]", "cogwheel[axis=x]",
        )
        commands.extend(f"/setblock {valve.coord(at)} create:{name}"
                        for at, name in zip(assembly, names, strict=True))
    with fixture_world(args, "ValveActionTicks", render=True, pack=args.pack) as control:
        control.commands(commands)
        control.step_to(control.clock() + 1)
        start = control.clock()
        differences = []
        for raw in rows:
            tick, index = map(int, raw[:2])
            if index == 0:
                if tick:
                    control.step_to(start + tick)
                if tick == 1:
                    control.commands(f"/data merge block {valve.coord(pos)} {{ScrollValue:{value}}}"
                                     for pos, _, _, value, _ in CASES)
                if tick == 2:
                    for pos, face, rear, _, sneak in CASES:
                        press(control, pos, face, rear, sneak)
                    if control.clock() != start + tick:
                        raise RuntimeError("The simulation advanced while the player released use.")
            actual = measure(control, assemblies[index])
            expected = tuple(map(float, raw[2:]))
            if actual != expected:
                differences.append((tick, index, expected, actual))
        if differences:
            raise RuntimeError(f"{len(differences)} Java differences: {differences[:10]}.")
    print("Valve matches 48 Java samples including both release-action ticks and two transmitted gear ratios.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    compare(parser.parse_args())


if __name__ == "__main__":
    main()
