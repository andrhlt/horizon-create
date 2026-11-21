#!/usr/bin/env python3
"""Verify idle and loaded gauge networks survive a cold world reopen."""

import argparse
import re
from pathlib import Path

from fixture_world import fixture_world


ACTIVE = ((6, 100, -10), (6, 101, -10), (6, 102, -10), (6, 103, -10))
IDLE = ((12, 100, -10), (13, 100, -10))


def coords(pos):
    return " ".join(map(str, pos))


def tag(control, pos):
    return control.command(f"/data get block {coords(pos)}")


def values(control, pos):
    output = tag(control, pos)
    return tuple(float(re.search(rf"\b{key}: (-?[\d.]+)f", output)[1])
                 for key in ("Speed", "Capacity", "Stress"))


def step(control, ticks):
    for _ in range(ticks):
        control.step_to(control.clock() + 1)


def verify(args):
    with fixture_world(args, "GaugeReopen", pack=args.pack) as control:
        control.commands((
            "/fill 9 100 -12 12 100 -8 minecraft:smooth_stone",
            "/fill 7 99 -13 7 99 -8 minecraft:smooth_stone",
            "/fill 6 100 -13 6 100 -8 minecraft:smooth_stone",
            "/fill 8 100 -13 8 100 -8 minecraft:smooth_stone",
            "/setblock 7 100 -13 minecraft:smooth_stone",
            "/setblock 7 100 -8 minecraft:smooth_stone",
            "/setblock 6 100 -10 create:water_wheel[facing=up]",
            "/setblock 6 101 -10 create:cogwheel[axis=y]",
            "/setblock 6 102 -10 create:stressometer[facing=east,axis_along_first=true]",
            "/setblock 6 103 -10 create:speedometer[facing=east,axis_along_first=true]",
            "/setblock 7 100 -9 minecraft:water",
            "/fill 6 101 -9 6 101 -3 create:millstone",
            "/setblock 12 100 -10 create:stressometer[facing=east,axis_along_first=true]",
            "/setblock 13 100 -10 create:speedometer[facing=east,axis_along_first=true]",
        ))
        step(control, 70)
        step(control, 3)
        before_active = [values(control, pos) for pos in ACTIVE]
        before_idle = [values(control, pos) for pos in IDLE]
        if before_active != [(8.0, 256.0, 224.0)] * 4:
            raise RuntimeError(f"Loaded gauge network before reopen was unexpected: {before_active}")
        if before_idle != [(0.0, 0.0, 0.0)] * 2:
            raise RuntimeError(f"Idle gauges before reopen were unexpected: {before_idle}")

        control.restart()
        step(control, 3)
        after_active = [values(control, pos) for pos in ACTIVE]
        after_idle = [values(control, pos) for pos in IDLE]
        if after_active != before_active:
            raise RuntimeError(f"Loaded gauge network changed after reopen: {after_active}, expected {before_active}")
        if after_idle != before_idle:
            raise RuntimeError(f"Idle gauges changed after reopen: {after_idle}, expected {before_idle}")
    print("Idle gauges and the running 8 RPM, 224/256 SU gauge network survived save/reopen.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
