#!/usr/bin/env python3
"""Check retained Creative Motor capacity and Millstone stress semantics."""

import argparse
from math import isclose
from pathlib import Path
import re

from fixture_world import fixture_world

MOTOR = (0, 99, 0)
MILLSTONE = (0, 100, 0)


def xyz(pos):
    return " ".join(map(str, pos))


def read_float(data, key):
    match = re.search(rf"\b{key}: (-?[\d.]+)f?", data)
    if match is None:
        raise RuntimeError(f"Missing {key} in block data: {data}")
    return float(match[1])


def run(args):
    with fixture_world(args, "TypedKineticStress", pack=args.pack) as control:
        control.commands((
            f"/setblock {xyz(MOTOR)} create:creative_motor[facing=up]",
            f"/setblock {xyz(MILLSTONE)} create:millstone",
        ))
        for _ in range(4):
            control.step_to(control.clock() + 1)
        data = control.command(f"/data get block {xyz(MILLSTONE)}")
        capacity = read_float(data, "Capacity")
        stress = read_float(data, "Stress")
        speed = read_float(data, "Speed")
        if not isclose(capacity, 262144.0, abs_tol=1e-5):
            raise RuntimeError(f"Expected 16 RPM motor capacity 262144, got {capacity}: {data}")
        if not isclose(stress, 64.0, abs_tol=1e-5):
            raise RuntimeError(f"Expected Millstone stress 64 at 16 RPM, got {stress}: {data}")
        if not isclose(speed, 16.0, abs_tol=1e-5):
            raise RuntimeError(f"Expected unoverloaded network speed 16, got {speed}: {data}")
    print("Typed kinetic network published Java motor capacity 262144 and Millstone stress 64 at 16 RPM.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
