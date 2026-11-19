#!/usr/bin/env python3
"""Compare a loaded two-controller chain under forward and reverse Java power."""

import argparse
import csv
from math import isclose
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

FIRST = (10, 101, -10)
FIRST_COG = (10, 102, -10)
LINK = (10, 102, -9)
SECOND = (10, 102, -8)
SECOND_COG = (10, 103, -8)
OUTPUT = (11, 103, -8)
MOTOR = (9, 101, -10)
REVERSE = (9, 103, -8)
FANS = ((11, 101, -10, "east"), (10, 102, -7, "south"), (12, 103, -8, "east"))
SETTINGS = {5: (FIRST, 48), 12: (SECOND, -32), 22: (FIRST, 64), 30: (SECOND, 12)}


def coords(pos):
    return " ".join(map(str, pos))


def tag(text, key):
    return float(re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", text)[1])


def sample(control, tick):
    first, first_cog, middle, second, second_cog, output = control.commands(
        f"/data get block {coords(pos)}" for pos in (FIRST, FIRST_COG, LINK, SECOND, SECOND_COG, OUTPUT)
    )
    return (tick, tag(first, "ScrollValue"), tag(second, "ScrollValue"),
            *(tag(nbt, "Speed") for nbt in (first, first_cog, middle, second, second_cog, output)),
            *(tag(nbt, key) for nbt in (first, second) for key in ("Stress", "Capacity")))


def verify(args, header, expected):
    with fixture_world(args, "SpeedControllerCascade", pack=args.pack) as control:
        control.commands((
            "/fill 6 100 -13 13 104 -6 minecraft:air",
            "/fill 6 100 -13 13 100 -6 minecraft:smooth_stone",
            "/tp @s 6.5 101 -10",
            f"/setblock {coords(FIRST)} create:rotation_speed_controller[axis=x]",
            f"/setblock {coords(FIRST_COG)} create:large_cogwheel[axis=z]",
            f"/setblock {coords(LINK)} create:shaft[axis=z]",
            f"/setblock {coords(SECOND)} create:rotation_speed_controller[axis=z]",
            f"/setblock {coords(SECOND_COG)} create:large_cogwheel[axis=x]",
            f"/setblock {coords(OUTPUT)} create:shaft[axis=x]",
            *(f"/setblock {coords(pos[:3])} create:encased_fan[facing={pos[3]}]" for pos in FANS),
            f"/setblock {coords(MOTOR)} create:creative_motor[facing=east]",
            f"/data merge block {coords(MOTOR)} {{ScrollValue:24}}",
        ))
        start = control.clock()
        actual = []
        differences = []
        for row in expected:
            tick = int(row[0])
            control.step_to(start + tick)
            values = sample(control, tick)
            actual.append(values)
            for column, want, got in zip(header, row, values, strict=True):
                if not isclose(float(want), got, abs_tol=0.0001, rel_tol=0.0):
                    differences.append((tick, column, want, got))
            if (setting := SETTINGS.get(tick)) is not None:
                pos, value = setting
                control.command(f"/data merge block {coords(pos)} {{ScrollValue:{value}}}")
            if tick == 16:
                control.command(f"/setblock {coords(MOTOR)} minecraft:air")
            if tick == 18:
                control.commands((
                    f"/setblock {coords(REVERSE)} create:creative_motor[facing=east]",
                    f"/data merge block {coords(REVERSE)} {{ScrollValue:40}}",
                ))
            if tick == 36:
                control.command(f"/data merge block {coords(REVERSE)} {{ScrollValue:20}}")

    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    if differences:
        raise RuntimeError(f"{len(differences)} differences. First 20: {differences[:20]}")
    print(f"Both cascaded controllers, loaded speeds, and network totals matched Java for {len(actual)} simulated ticks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/rotation-speed-controller-cascade-horizon.csv")
    args = parser.parse_args()
    with (ROOT / "fixtures/rotation-speed-controller-cascade-java.csv").open() as stream:
        header, _initialization, *expected = list(csv.reader(stream))
    verify(args, header, expected)


if __name__ == "__main__":
    main()
