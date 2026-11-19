#!/usr/bin/env python3
"""Run Create's 3_pipe_split and 3_pipe_combine fixtures at every Java tick."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

PUMP = "5 97 -10"
TANKS = ("4 97 -10", "8 97 -11", "8 97 -10", "8 97 -9")


def reading(text, field):
    match = re.search(rf'\b{field}:\s*(-?\d+(?:\.\d+)?)', text)
    return float(match[1]) if match else 0


def sample(control, mode, tick):
    pump, *tanks = control.commands((
        f"/data get block {PUMP}",
        *(f"/data get block {tank} TankContent" for tank in TANKS),
    ))
    if "create:mechanical_pump" not in pump:
        raise RuntimeError(f"The fixture did not load its pump: {pump}")
    if any("has the following block data" not in tank for tank in tanks):
        raise RuntimeError(f"The fixture did not load its four tank controllers: {tanks}")
    return [mode, str(tick), f'{reading(pump, "Speed"):.7f}',
            *(str(int(reading(tank, "amount"))) for tank in tanks)]


def run(args):
    with (ROOT / "fixtures/branched_pipes-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    actual = []
    for mode, face in (("combine", "east"), ("split", "west")):
        name = f"gametest/fluids/3_pipe_{mode}"
        count = sum(row[0] == mode for row in expected)
        if args.mode and mode != args.mode:
            continue
        with fixture_world(args, f"Pipe-{mode}", Path(name + ".nbt")) as control:
            control.command(f"/place template create:{name} 3 96 -12")
            control.command(f"/setblock {PUMP} create:mechanical_pump[facing={face},waterlogged=false]")
            start = control.clock()
            for tick in range(count):
                if tick:
                    control.step_to(start + tick)
                actual.append(sample(control, mode, tick))

    suffix = f"-{args.mode}" if args.mode else ""
    path = ROOT / f".local/branched_pipes{suffix}-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    if args.mode:
        expected = [row for row in expected if row[0] == args.mode]
    differences = [(a, b) for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"Branched pipe differs on {len(differences)} rows. "
                         f"First rows (Java, Horizon): {differences[:10]}. See {path}")
    print(f"Branched fluid transfer matched {len(actual)} Java ticks. See {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--mode", choices=("split", "combine"))
    run(parser.parse_args())


if __name__ == "__main__":
    main()
