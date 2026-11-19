#!/usr/bin/env python3
"""Compare glue-free Windmills in all six orientations against Java ticks."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from itertools import groupby

from fixture_world import ROOT, fixture_world

windmill = import_module("test-windmill")
DIRECTIONS = {
    "down": (0, -1, 0), "up": (0, 1, 0), "north": (0, 0, -1),
    "south": (0, 0, 1), "west": (-1, 0, 0), "east": (1, 0, 0),
}
ORIGINS = {facing: (8 + index % 2 * 11, 180, 23 + index // 2 * 12)
           for index, facing in enumerate(DIRECTIONS)}


def offset(pos, direction, count=1):
    return tuple(a + b * count for a, b in zip(pos, direction, strict=True))


def parts(facing):
    pos = ORIGINS[facing]
    direction = DIRECTIONS[facing]
    axis = "xyz"[next(index for index, step in enumerate(direction) if step)]
    shaft = offset(pos, direction, -1)
    anchor = offset(pos, direction)
    tangent = DIRECTIONS["east" if axis == "y" else "up"]
    cross = DIRECTIONS["east" if axis == "z" else "south"]
    cells = [offset(offset(anchor, tangent, i // 4), cross, i % 4) for i in range(8)]
    return pos, shaft, cells, axis


def setup(control):
    control.commands(("/fill 3 177 17 26 177 53 minecraft:smooth_stone", "/gamemode survival"))
    for facing in DIRECTIONS:
        pos, shaft, cells, axis = parts(facing)
        x, y, z = pos
        walk = (x - 3, y - 1, z) if axis == "z" else (x, y - 1, z - 3)
        control.commands((
            f"/setblock {windmill.coords(walk)} minecraft:smooth_stone",
            f"/setblock {windmill.coords(pos)} create:windmill_bearing[facing={facing}]",
            f"/setblock {windmill.coords(shaft)} create:shaft[axis={axis}]",
            *(f"/setblock {windmill.coords(cell)} create:white_sail[facing={facing}]" for cell in cells),
        ))


def click(control, facing):
    (x, y, z), _, _, axis = parts(facing)
    if axis == "z":
        control.command(f"/tp @s {x - 2.5} {float(y)} {z + 0.5}")
        aim = (x + 0.02, y + 0.91, z + 0.5)
    else:
        control.command(f"/tp @s {x + 0.5} {float(y)} {z - 2.5}")
        aim = (x + 0.5, y + 0.91, z + 0.02)
    control.call("wait", 3)
    control.call("look-at", *aim)
    control.call("wait", 2)
    control.call("mouse", "right", "click")
    control.call("wait", 2)


def observe(control, facing, tick):
    pos, shaft, cells, _ = parts(facing)
    mill, shaft, *sails = control.commands((
        f"/data get block {windmill.coords(pos)}",
        f"/data get block {windmill.coords(shaft)}",
        *(f"/execute if block {windmill.coords(cell)} create:white_sail[facing={facing}]"
          for cell in cells),
    ))
    read = windmill.number
    return {
        "tick": tick, "facing": facing, "running": str(read(mill, "Running") == 1).lower(),
        "generated_rpm": read(mill, "LastGenerated"), "bearing_rpm": read(mill, "Speed"),
        "shaft_rpm": read(shaft, "Speed"), "angle": read(mill, "Angle"),
        "stress": read(mill, "Stress"), "capacity": read(mill, "Capacity"),
        "captured": int(read(mill, "Sails")),
        "present": sum(result.startswith("Test passed") for result in sails),
    }


def run(args):
    with (ROOT / "fixtures/windmill-facings-java.csv").open() as source:
        java = list(csv.DictReader(source))
    with fixture_world(args, "Windmill-facings", render=True, pack=args.pack) as control:
        setup(control)
        start = control.clock()
        for tick, expected in groupby(java, key=lambda row: int(row["tick"])):
            if tick:
                control.step_to(start + tick)
            if tick in (1, 11):
                for facing in DIRECTIONS:
                    click(control, facing)
            if tick == 7:
                control.commands(f"/data merge block {windmill.coords(pos)} {{ScrollValue:1}}"
                                 for pos in ORIGINS.values())
            for row in expected:
                windmill.compare(row, observe(control, row["facing"], tick))
    print(f"Matched {len(java)} Java windmill samples across all six facing directions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
