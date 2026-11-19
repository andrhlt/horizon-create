#!/usr/bin/env python3
"""Compare Create's original in-world pumping fixtures tick by tick."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

PUMP = "6 97 -10"
PIPE = "7 97 -10"
BASIN = "8 97 -10"
WORLD_END = "5 97 -10"


def compound(text, key):
    opening = re.search(rf'\b{key}:\s*\{{', text)
    if not opening:
        return ""
    begin = opening.end()
    depth = 1
    for index in range(begin, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[begin:index]
    raise ValueError(f"Unclosed {key} in {text}")


def number(text, key, default=0.0):
    match = re.search(rf'\b{key}:\s*(-?\d+(?:\.\d+)?)', text)
    return float(match[1]) if match else default


def progress(text, side):
    flow = compound(compound(text, side), "Flow")
    if not flow:
        return "0.0000000"
    return f'{number(compound(flow, "Progress"), "Value", 1.0):.7f}'


def sample(control, mode, tick):
    pump, pipe, basin, water = control.commands((
        f"/data get block {PUMP}",
        f"/data get block {PIPE}",
        f"/data get block {BASIN} InputTanks",
        f"/execute if block {WORLD_END} minecraft:water",
    ))
    if "create:mechanical_pump" not in pump or "create:glass_fluid_pipe" not in pipe:
        raise RuntimeError(f"Could not read template pump and pipe: {pump}, {pipe}")
    if not water.startswith(("Test passed", "Test failed")):
        raise RuntimeError(f"Could not read the open pipe's water: {water}")
    buffer = compound(compound(pump, "west"), "OpenEnd")
    return [
        mode, str(tick), f'{number(pump, "Speed"):.7f}',
        "minecraft:water" if water.startswith("Test passed") else "minecraft:air",
        str(int(number(basin, "amount"))),
        *(progress(part, side) for part in (pump, pipe) for side in ("east", "west")),
        str(int(number(compound(buffer, "Fluid"), "amount"))),
    ]


def run(args):
    path = ROOT / "fixtures/world_pump-java.csv"
    with path.open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    actual = []
    for mode in ("in", "out"):
        structure = f"gametest/fluids/in_world_pumping_{mode}"
        count = sum(row[0] == mode for row in expected)
        with fixture_world(args, f"World-pump-{mode}", Path(structure + ".nbt")) as control:
            control.command(f"/place template create:{structure} 3 96 -12")
            control.command("/setblock 7 98 -9 minecraft:lever[face=floor,facing=west,powered=false]")
            start = control.clock()
            for tick in range(count):
                if tick:
                    control.step_to(start + tick)
                actual.append(sample(control, mode, tick))

    output = ROOT / ".local/world_pump-horizon.csv"
    with output.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"World pump differs on {len(differences)} rows. "
                         f"First rows (Java, Horizon): {differences[:10]}. See {output}")
    print(f"Both open pipe fixtures matched {len(actual)} Java ticks. See {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())


if __name__ == "__main__":
    main()
