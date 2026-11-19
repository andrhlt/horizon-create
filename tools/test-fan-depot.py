#!/usr/bin/env python3
"""Compare original Java Depot fan processes through a power interruption."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/wheat_milling.nbt")
LANES = (
    (-11, "minecraft:oak_leaves[persistent=true,waterlogged=true]", "minecraft:magenta_wool", "minecraft:white_wool"),
    (-7, "minecraft:campfire[lit=true]", "minecraft:beef", "minecraft:cooked_beef"),
    (-3, "minecraft:soul_campfire[lit=true]", "minecraft:sand", "minecraft:soul_sand"),
    (1, "minecraft:lava[level=0]", "minecraft:raw_iron", "minecraft:iron_ingot"),
)

INDUSTRIAL_LANE = ((-11, "minecraft:oak_leaves[persistent=true,waterlogged=true]",
                   "create:industrial_iron_block", "create:weathered_iron_block"),)

RUNTIME_WASHING_LANES = tuple(
    (-11 + 4 * index, "minecraft:oak_leaves[persistent=true,waterlogged=true]",
     f"minecraft:{color}_concrete_powder", f"minecraft:{color}_concrete")
    for index, color in enumerate(("blue", "red"))
)


def configure(control, lanes):
    commands = []
    for z, catalyst, _, _ in lanes:
        commands.extend((
            f"/setblock 4 106 {z} create:creative_motor[facing=east]",
            f"/data merge block 4 106 {z} {{ScrollValue:256}}",
            f"/setblock 5 106 {z} create:encased_fan[facing=east]",
            f"/setblock 6 105 {z} minecraft:stone",
            f"/setblock 6 106 {z - 1} minecraft:stone",
            f"/setblock 6 106 {z + 1} minecraft:stone",
            f"/setblock 7 106 {z} minecraft:oak_sign",
            f"/setblock 6 106 {z} {catalyst}",
            f"/setblock 7 105 {z} create:depot",
        ))
    control.commands(commands)
    start = control.clock()
    for tick in range(1, 6):
        control.step_to(start + tick)
    replies = control.commands(f"/item replace block 7 105 {z} container.0 with {item}"
                               for z, _, item, _ in lanes)
    if any("Replaced 1 slot" not in message for message in replies):
        raise RuntimeError(f"Could not load fan inputs: {replies}")


def sample(control, tick, lanes):
    replies = control.commands(
        cmd for z, *_ in lanes for cmd in (f"/data get block 5 106 {z}", f"/data get block 7 105 {z}")
    )
    for i, ((_, _, source, into), fan, depot) in enumerate(zip(lanes, replies[::2], replies[1::2], strict=True)):
        speed = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)", fan)
        if not speed or "create:depot" not in depot:
            raise RuntimeError(f"Could not sample fan lane {i}: {fan}, {depot}")
        kind = re.search(r'\bFanProcessingType: "([^"]+)"', depot)
        remaining = re.search(r"\bFanProcessingTime: (-?\d+)", depot)
        items = re.search(r"\bItems: (\[[^\]]*\])", depot)
        carried = items[1] if items else ""
        input_count = int(f'"{source}"' in carried)
        output_count = int(f'"{into}"' in carried)
        yield [str(tick), str(i), str(int(float(speed[1]))), str(input_count), str(output_count),
               kind[1] if kind else "_", remaining[1] if remaining else "0"]


def run(args):
    if args.runtime_washing:
        lanes = RUNTIME_WASHING_LANES
        name = "runtime-washing"
    elif args.industrial:
        lanes = INDUSTRIAL_LANE
        name = "fan_metal"
    else:
        lanes = LANES
        name = "fan_depot"
    visual = not (args.industrial or args.runtime_washing)
    with (ROOT / f"fixtures/{name}-java.csv").open() as file:
        rows = csv.reader(file)
        header, expected = next(rows), list(rows)
    actual = []
    world = "Runtime-washing" if args.runtime_washing else "Fan-depot"
    with fixture_world(args, world, STRUCTURE, render=visual, pack=args.pack) as control:
        configure(control, lanes)
        start = control.clock()
        for tick in range(len(expected) // len(lanes)):
            if tick:
                control.step_to(start + tick)
            actual.extend(sample(control, tick, lanes))
            if tick in (60, 68):
                speed = 0 if tick == 60 else 256
                control.commands(f"/data merge block 4 106 {z} {{ScrollValue:{speed}}}" for z, *_ in lanes)
        if visual:
            control.command("/fill 3 104 -15 11 104 4 minecraft:smooth_stone")
            control.command("/time set noon")
            control.call("tp", 10.5, 105, -7.5)
            control.call("look-at", 6, 106, -8)
            control.call("key", "f1", "tap")
            control.call("wait", 4)
            control.call("screenshot", ROOT / ".local/fan_depot.png")

    path = ROOT / ".local" / f"{name}-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"Fan differs in {len(differences)} rows. "
                         f"First rows (Java, Horizon): {differences[:5]}. See {path}")
    print(f"Fan processing matched {len(actual) // len(lanes)} Java ticks across {len(lanes)} lanes. See {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--industrial", action="store_true")
    mode.add_argument("--runtime-washing", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
