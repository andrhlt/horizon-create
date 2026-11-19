#!/usr/bin/env python3
"""Compare casing and uncasing powered shafts through Java’s measured tick sequence."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

SHAFT = "create:shaft"
WRENCH = "create:wrench"
LANES = (((8, 101, -10), "x", "east", (7, 101, -10), (9, 101, -10), 24, "andesite"),
         ((16, 101, -10), "z", "south", (16, 101, -11), (16, 101, -9), 40, "brass"))


def coords(pos):
    return " ".join(map(str, pos))


def setup(control):
    control.commands((
        "/fill 4 100 -15 20 100 -7 minecraft:smooth_stone",
        "/fill 4 101 -15 20 104 -7 minecraft:air",
        "/gamemode survival",
        f"/item replace entity @s hotbar.1 with {WRENCH} 1",
    ))
    for pos, axis, facing, begin, end, rpm, material in LANES:
        control.commands((
            f"/setblock {coords(pos)} {SHAFT}[axis={axis},waterlogged={'true' if material == 'andesite' else 'false'}]",
            f"/setblock {coords(end)} {SHAFT}[axis={axis}]",
            f"/setblock {coords(begin)} create:creative_motor[facing={facing}]",
            f"/data merge block {coords(begin)} {{ScrollValue:{rpm}}}",
            f"/item replace entity @s hotbar.{0 if material == 'andesite' else 2} with create:{material}_casing 2",
        ))


def apply(control, case, wrench=False, *, teleport=True):
    pos, _, _, _, _, _, material = LANES[case]
    x, y, z = pos
    if teleport:
        control.command(f"/tp @s {x + 0.5:.2f} {y} {z - 2.1:.2f}")
        control.call("wait", 3)
    control.call("select", WRENCH if wrench else f"create:{material}_casing")
    if wrench:
        control.call("key", "shift", "down")
        control.call("wait", 3)
    control.call("look-at", x + 0.5, y + (0.999 if wrench else 0.685), z + 0.5)
    control.call("wait", 2)
    control.call("mouse", "right", "down")
    control.call("wait", 1)
    control.call("mouse", "right", "up")
    if wrench:
        control.call("key", "shift", "up")
    control.call("wait", 4)


def sample(control, tick, index):
    pos, _, _, _, end, _, material = LANES[index]
    state = control.call("block", *pos)["state"]
    block = state.split("[", 1)[0]
    name = "shaft" if block == SHAFT else "encased" if block == f"create:{material}_encased_shaft" else "other"
    axis = re.search(r"\baxis=([xyz])\b", state)
    wet = "true" if "waterlogged=true" in state else "false"
    remaining = control.call("inventory")["counts"].get(f"create:{material}_casing", 0)
    nbt = control.command(f"/data get block {coords(end)} Speed")
    speed = re.search(r"(-?\d+\.\d+)f\b", nbt)[1]
    return (str(tick), str(index), name, axis[1] if axis else "none", wet,
            str(remaining), f"{float(speed):.4f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/shaft-casing-horizon.csv")
    args = parser.parse_args()
    with (ROOT / "fixtures/shaft-casing-java.csv").open() as stream:
        header, _, _, *rows = list(csv.reader(stream))

    actual = []
    with fixture_world(args, "ShaftCasing", render=True, pack=args.pack) as control:
        setup(control)
        start = control.clock()
        for row in rows:
            tick, index = map(int, row[:2])
            if index == 0:
                control.step_to(start + tick)
            actual.append(sample(control, tick, index))
            if tick in (3, 7):
                apply(control, index, wrench=tick == 7)
    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    expected = list(map(tuple, rows))
    if actual != expected:
        differences = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
        raise RuntimeError(f"{len(differences)} shaft casing mismatches. First six: {differences[:6]}")
    print(f"Both shaft materials matched Java through casing and uncasing across {len(actual) // 2} simulated ticks.")


if __name__ == "__main__":
    main()
