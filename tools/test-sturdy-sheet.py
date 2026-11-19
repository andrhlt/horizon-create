#!/usr/bin/env python3
"""Fill powdered obsidian with lava and finish both Java press operations."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/wheat_milling.nbt")
SPOUT = "5 106 -11"
SOURCE = "5 104 -11"
PRESS = "8 106 -11"
MOTOR = "7 106 -11"
DESTINATION = "8 104 -11"


def number(text, key, default=0):
    found = re.search(rf'\b{key}: (-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)', text)
    return int(float(found[1])) if found else default


def stack(text):
    identity = re.findall(r'\bid: "([^"]+)"', text)
    return [identity[-1] if identity else "minecraft:air", str(number(text, "step"))]


def sample(control, tick):
    spout, press, source, destination = control.commands((
        f"/data get block {SPOUT}",
        f"/data get block {PRESS}",
        f"/data get block {SOURCE} Items",
        f"/data get block {DESTINATION} Items",
    ))
    return [
        str(tick), str(number(spout, "ProcessingTicks", -1)), str(number(spout, "amount")),
        *(str(number(press, key)) for key in ("Speed", "Running", "Finished", "Ticks")),
        *stack(source), *stack(destination),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    with (ROOT / "fixtures/sturdy_sheet-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    actual = []
    with fixture_world(args, "Sturdy-sheet", STRUCTURE) as control:
        control.commands((
            f"/setblock {SOURCE} create:depot",
            f"/setblock {SPOUT} create:spout",
            f"/setblock {DESTINATION} create:depot",
            f"/setblock {PRESS} create:mechanical_press[facing=east]",
            f"/setblock {MOTOR} create:creative_motor[facing=east]",
            f"/data merge block {MOTOR} {{ScrollValue:128}}",
        ))
        control.step_to(control.clock() + 1)
        control.commands((
            f'/data merge block {SPOUT} {{Tanks:[{{TankContent:{{Fluid:{{id:"minecraft:lava",amount:1000}}}}}}]}}',
            f"/item replace block {SOURCE} container.0 with create:powdered_obsidian",
        ))
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
            if tick == 30:
                control.commands((
                    f"/item replace block {DESTINATION} container.0 from block {SOURCE} container.0",
                    f"/item replace block {SOURCE} container.0 with minecraft:air",
                ))

    output = ROOT / ".local/sturdy_sheet-horizon.csv"
    with output.open("w") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a[0], {k: (x, y) for k, x, y in zip(header, a, b, strict=True) if x != y})
                   for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"Sturdy Sheet differs on {len(differences)} ticks. "
                         f"First differences (Java, Horizon): {differences[:8]}. See {output}")
    print(f"Sturdy Sheet assembly matched all {len(expected)} Java ticks. See {output}")


if __name__ == "__main__":
    main()
