#!/usr/bin/env python3
"""Trace the original passive steam engine GameTest in Horizon."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/fluids/steam_engine.nbt")


def value(text, key, default=0.0):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", text)
    return float(match[1]) if match else default


def sample(control, tick):
    tank, pump_a, pump_b, shaft_a, shaft_b, speed, stress = control.commands((
        "/data get block 4 98 -11 Boiler",
        "/data get block 6 98 -11",
        "/data get block 6 98 -10",
        "/data get block 4 98 -7",
        "/data get block 5 98 -7",
        "/data get block 7 97 -7",
        "/data get block 8 97 -7",
    ))
    numbers = (
        value(pump_a, "Speed"), value(pump_b, "Speed"),
        value(shaft_a, "Speed"), value(shaft_a, "EnginePower"),
        value(shaft_b, "Speed"), value(shaft_b, "EnginePower"),
        value(speed, "Speed"), value(stress, "Capacity"),
    )
    return [str(tick), f'{value(tank, "Supply"):.4f}', str(int(value(tank, "Engines"))),
            str(int(value(tank, "ActiveHeat"))), str(bool(value(tank, "PassiveHeat"))).lower(),
            *(f"{n:.4f}" for n in numbers)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    args = parser.parse_args()
    with (ROOT / "fixtures/steam_engine-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    readings = {}
    with fixture_world(args, "Steam-engine", STRUCTURE) as control:
        control.command("/place template create:gametest/fluids/steam_engine 3 96 -12")
        control.command("/setblock 7 98 -9 minecraft:lever[face=floor,facing=west,powered=false]")
        start = control.clock()
        for tick in range(int(expected[-1][0]) + 4):
            if tick:
                control.step_to(start + tick)
            readings[str(tick)] = sample(control, tick)
    path = ROOT / ".local/steam_engine-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(readings.values())
    differences = [(row, readings[row[0]]) for row in expected if row != readings[row[0]]]
    if differences:
        raise SystemExit(f"Steam engine differs on {len(differences)} ticks. First rows "
                         f"(Java, Horizon): {differences[:5]}. See {path}")
    print(f"Original steam engine matched Java across {len(expected)} ticks. See {path}")


if __name__ == "__main__":
    main()
