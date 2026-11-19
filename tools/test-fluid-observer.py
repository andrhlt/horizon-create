#!/usr/bin/env python3
"""Compare the original Smart Observer detecting water in a pipe."""

import argparse
import csv
import json
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/fluids/smart_observer_pipes.nbt")


def field(text, key):
    match = re.search(rf"\b{key}: (\d+)", text)
    return match[1] if match else "0"


def sample(control, tick):
    nbt = [
        "/data get block 8 97 -8 TankContent",
        "/data get block 4 97 -8 TankContent",
        "/data get block 6 97 -9 TurnOff",
    ]
    actions = [*("command " + json.dumps(line) for line in nbt),
               "block 6 97 -9", "block 6 97 -8", "block 6 99 -8"]
    source, dest, timer, detector, piston, diamond = control.call(
        "script", script="\n".join(actions) + "\n",
    )
    return [str(tick), field(source["chat"][-1], "amount"), field(dest["chat"][-1], "amount"),
            timer["chat"][-1].rsplit(": ", 1)[-1],
            str("powered=true" in detector["state"]).lower(),
            str("extended=true" in piston["state"]).lower(),
            str(diamond["state"] == "minecraft:diamond_block").lower()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    args = parser.parse_args()
    with (ROOT / "fixtures/smart_observer_pipes-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    actual = []
    with fixture_world(args, "Fluid-observer", STRUCTURE) as control:
        control.command("/place template create:gametest/fluids/smart_observer_pipes 3 96 -12")
        control.command("/setblock 6 98 -11 minecraft:lever[face=floor,facing=west,powered=false]")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
    path = ROOT / ".local/smart_observer_pipes-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"Fluid observer differs on {len(differences)} ticks. First (Java, Horizon): "
                         f"{differences[:5]}. See {path}")
    print(f"Fluid observer matched all {len(expected)} ticks. See {path}")


if __name__ == "__main__":
    main()
