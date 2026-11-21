#!/usr/bin/env python3
"""Replay Create's original fan_processing GameTest with its seeded gravel roll."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/items/fan_processing.nbt")
LANES = tuple(zip((6, 8, 10, 12, 14), (4, 8, 10, 12, 14)))
STACK = re.compile(r'\{[^{}]*?\b(?:Count|count): (\d+)[^{}]*?\bid: "([\w:]+)"[^{}]*?\}')
COUNT = re.compile(r'\b(?:Count|count): (\d+)')


def sample(control, tick):
    responses = []
    for x, lamp_x in LANES:
        responses.extend(control.commands((
            f"/data get block {x} 101 -9 Items",
            f"/data get block {x} 100 -9 Items",
            f"/data get block {x} 98 -9 Items",
            f"/data get block {x} 97 -9 Items",
            f"/execute if block {lamp_x} 97 -11 minecraft:redstone_lamp[lit=true]",
        )))
    values = iter(responses)
    records = []
    for lane in range(len(LANES)):
        supply, upper, lower, receiver, lamp = (next(values) for _ in range(5))
        match = STACK.search(lower)
        if COUNT.search(lower) and not match:
            raise RuntimeError(f"Could not read lower chute in lane {lane}: {lower}")
        if not lamp.startswith(("Test passed", "Test failed", "Nothing happened")):
            raise RuntimeError(f"Could not read the lamp in lane {lane}: {lamp}")
        counts = [str(sum(map(int, COUNT.findall(items)))) for items in (supply, upper, receiver)]
        records.append([str(tick), str(lane), counts[0], counts[1],
                        match[2] if match else "_", match[1] if match else "0",
                        counts[2], "1" if lamp.startswith("Test passed") else "0"])
    return records


def run(args):
    with (ROOT / "fixtures/fan_processing-java.csv").open() as file:
        rows = csv.reader(file)
        header, expected = next(rows), list(rows)
    actual = []
    with fixture_world(args, "Fan-processing", STRUCTURE, env={"CREATE_FAN_TRACE_SEED": "4096"}) as control:
        control.command("/place template create:gametest/items/fan_processing 3 96 -12")
        control.command("/fill 5 102 -9 14 102 -9 minecraft:redstone_wire")
        control.command("/setblock 4 102 -9 minecraft:lever[face=floor,facing=south,powered=false]")
        start = control.clock()
        for tick in range(len(expected) // len(LANES)):
            if tick:
                control.step_to(start + tick)
            actual.extend(sample(control, tick))

    path = ROOT / ".local/fan_processing-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"Loose item fan differs on {len(differences)} rows. "
                         f"First rows (Java, Horizon): {differences[:12]}. See {path}")
    print(f"Loose item fan matched Java across {len(actual) // len(LANES)} ticks and {len(LANES)} lanes. See {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())


if __name__ == "__main__":
    main()
