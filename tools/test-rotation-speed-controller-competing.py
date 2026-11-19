#!/usr/bin/env python3
"""Replay Java speed-controller conflicts from a newly inserted motor."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world


def coordinates(pos):
    return " ".join(map(str, pos))


LAYOUTS = [
    [(x, 101, -10), (x, 102, -10), (x - 1, 101, -10), (x, 102, -11)]
    for x in (10, 16)
]


def sample(control, tick, case):
    states = [control.call("block", *pos)["state"] for pos in LAYOUTS[case]]
    exists = [int(state.startswith("create:")) for state in states]
    data = control.commands(
        f"/data get block {coordinates(pos)}" for pos, available in zip(LAYOUTS[case], exists)
        if available
    )
    speed = [float(re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)", nbt)[1]) for nbt in data]
    values = iter(speed)
    return (tick, case, *exists, *(next(values) if present else 0.0 for present in exists))


def verify(args, header, expected):
    with fixture_world(args, "SpeedControllerCompetingMotor", pack=args.pack) as control:
        control.commands((
            "/fill 5 100 -13 20 104 -8 minecraft:air",
            "/fill 5 100 -13 20 100 -8 minecraft:smooth_stone",
            "/tp @s 6 101 -10",
        ))
        for controller, cog, lower, _ in LAYOUTS:
            control.commands((
                f"/setblock {coordinates(controller)} create:rotation_speed_controller[axis=x]",
                f"/setblock {coordinates(cog)} create:large_cogwheel[axis=z]",
                f"/setblock {coordinates(lower)} create:creative_motor[facing=east]",
                f"/data merge block {coordinates(lower)} {{ScrollValue:24}}",
            ))
        start = control.clock()
        actual = []
        differences = []
        for row in expected:
            tick, case = map(int, row[:2])
            if case == 0:
                control.step_to(start + tick)
            values = sample(control, tick, case)
            actual.append(values)
            for column, want, got in zip(header, row, values, strict=True):
                if abs(float(want) - got) > 0.0001:
                    differences.append((tick, case, column, want, got))
            upper = coordinates(LAYOUTS[case][-1])
            if tick == 5:
                control.commands((
                    f"/setblock {upper} create:creative_motor[facing=south]",
                    f"/data merge block {upper} {{ScrollValue:{40 if case == 0 else -40}}}",
                ))
            if tick == 15:
                control.command(f"/setblock {upper} minecraft:air")
    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    if differences:
        raise RuntimeError(f"{len(differences)} differences. First 12: {differences[:12]}")
    print(f"Both competing-motor networks matched Java across {len(actual) // 2} simulated ticks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/rotation-speed-controller-competing-horizon.csv")
    args = parser.parse_args()
    with (ROOT / "fixtures/rotation-speed-controller-competing-java.csv").open() as stream:
        header, _, _, *expected = list(csv.reader(stream))
    verify(args, header, expected)


if __name__ == "__main__":
    main()
