#!/usr/bin/env python3
"""Replay a water-wheel controller network at and above its stress limit."""

import argparse
import csv
from importlib import import_module
from math import isclose
from pathlib import Path
import time

from fixture_world import ROOT, fixture_world

settings = import_module("test-rotation-speed-controller")
tag = settings.tag
coords = settings.coords

WHEEL = (6, 100, -10)
CONTROLLER = (7, 101, -10)
COG = (7, 102, -10)
FAN = (7, 102, -11)
GAUGE = (7, 102, -9)
SETTINGS = {2: 127, 4: 128, 6: 129, 8: 128, 10: -129, 12: -127}


def setup(world):
    world.commands((
        "/fill 6 100 -13 8 103 -8 minecraft:air",
        "/fill 7 99 -13 7 99 -8 minecraft:smooth_stone",
        "/fill 6 100 -13 6 100 -8 minecraft:smooth_stone",
        "/fill 8 100 -13 8 100 -8 minecraft:smooth_stone",
        "/setblock 7 100 -13 minecraft:smooth_stone",
        "/setblock 7 100 -8 minecraft:smooth_stone",
        f"/setblock {coords(WHEEL)} create:water_wheel[facing=up]",
        "/setblock 6 101 -10 create:gearbox[axis=z]",
        f"/setblock {coords(CONTROLLER)} create:rotation_speed_controller[axis=x]",
        f"/setblock {coords(COG)} create:large_cogwheel[axis=z]",
        f"/setblock {coords(FAN)} create:encased_fan[facing=north]",
        f"/setblock {coords(GAUGE)} create:speedometer[facing=east,axis_along_first=false]",
        "/setblock 7 100 -9 minecraft:water",
        "/tp @s 10.5 101 -10.5",
    ))
    start = world.clock() + 70
    world.command("/tick step 70")
    deadline = time.monotonic() + 10
    while (now := world.clock()) != start:
        if now > start or time.monotonic() >= deadline:
            raise RuntimeError(f"Expected the wheel to settle at tick {start}; got {now}.")
        time.sleep(0.03)
    return start


def sample(world, tick):
    wheel, regulator, cog, fan, gauge = world.commands(
        f"/data get block {coords(pos)}" for pos in (WHEEL, CONTROLLER, COG, FAN, GAUGE)
    )
    capacity = tag(regulator, "Capacity", float)
    stress = tag(regulator, "Stress", float)
    fan_rpm = 0.0 if tag(fan, "Stress", float) > tag(fan, "Capacity", float) else tag(fan, "Speed", float)
    return (
        tick, tag(regulator, "ScrollValue", int), capacity, stress, str(stress > capacity).lower(),
        *(tag(nbt, "Speed", float) for nbt in (wheel, regulator, cog)),
        fan_rpm, tag(gauge, "Value", float),
    )


def verify(args):
    with (ROOT / "fixtures/rotation-speed-controller-overload-java.csv").open() as stream:
        header, *expected = list(csv.reader(stream))
    actual = []
    with fixture_world(args, "ControllerOverload", pack=args.pack) as world:
        start = setup(world)
        for tick in range(17):
            if tick:
                world.step_to(start + tick)
            actual.append(sample(world, tick))
            if tick in SETTINGS:
                world.command(f"/data merge block {coords(CONTROLLER)} {{ScrollValue:{SETTINGS[tick]}}}")
    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    differences = []
    for want, got in zip(expected, actual, strict=True):
        for name, value, result in zip(header, want, got, strict=True):
            same = value == result if isinstance(result, str) else isclose(float(value), result, rel_tol=0.0, abs_tol=0.00005)
            if not same:
                differences.append((want[0], name, value, result))
    if differences:
        raise RuntimeError(f"{len(differences)} stress and overload differences. First 15: {differences[:15]}")
    print(f"Controller stress, exact threshold and recovery matched Java across {len(actual)} samples.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/rotation-speed-controller-overload-horizon.csv")
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
