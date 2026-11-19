#!/usr/bin/env python3
"""Compare ordinary shaft and assisted pole placement with Java."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

SHAFT = "create:shaft"
SMALL = "create:cogwheel"
NAMES = {SHAFT: "shaft", SMALL: "small"}


def coords(pos):
    return " ".join(map(str, pos))


def at(pos, dx=0, dy=0, dz=0):
    return (pos[0] + dx, pos[1] + dy, pos[2] + dz)


def place(control, case):
    x, y, z = origin = (8 + case % 3 * 18, 101, -11 + case // 3 * 8)
    item = SMALL if case == 8 else SHAFT
    control.commands((
        f"/fill {x - 3} {y - 1} {z - 4} {x + 15} {y - 1} {z + 4} minecraft:smooth_stone",
        f"/fill {x - 3} {y} {z - 4} {x + 15} {y + 3} {z + 4} minecraft:air",
        f"/item replace entity @s hotbar.0 with {item} 2",
    ))

    if case < 6:
        target = origin
        support = at(origin, dx=1) if case in (0, 1, 5) else at(origin, dy=-1)
        control.command(f"/setblock {coords(support)} minecraft:stone")
        if case in (2, 3, 4):
            control.command(f"/setblock {coords(at(origin, dx=-1))} {SHAFT}[axis=x]")
        if case == 4:
            control.command(f"/setblock {coords(at(origin, dz=-1))} {SHAFT}[axis=z]")
        if case == 5:
            control.command(f"/setblock {coords(origin)} minecraft:water[level=0]")
        if case == 0:
            feet = (x + 0.55, y, z - 2.2)
            aim = (x + 1.002, y + 0.5, z + 0.5)
        elif case == 1:
            # Keep the camera stationary for the steep side click. The ray
            # clears the east edge of the platform before crossing its height.
            control.command(f"/setblock {x - 1} {y + 1} {z} minecraft:smooth_stone")
            feet = (x - 0.18, y + 2, z + 0.5)
            aim = (x + 1.002, y + 0.5, z + 0.5)
        elif case == 5:
            feet = (x - 2.0, y, z + 0.5)
            aim = (x + 1.002, y + 0.5, z + 0.5)
        else:
            feet = (x + 0.5, y, z + 1.55)
            aim = (x + 0.5, y - 0.002, z + 0.5)
    else:
        poles = 2 if case == 6 else 12 if case == 9 else 1
        control.commands(
            f"/setblock {coords(at(origin, dx=dist))} {SHAFT}[axis=x]" for dist in range(poles + 1)
        )
        if case == 7:
            control.command(f"/setblock {coords(at(origin, dx=2))} minecraft:stone")
        target = at(origin, dx=-1 if case in (7, 9) else poles + 1)
        feet = (x - 1.5, y, z + 0.5)
        aim = (x + 0.85, y + 0.685, z + 0.5)

    control.command("/tp @s " + " ".join(f"{value:.4f}" for value in feet))
    control.call("wait", 3)
    control.call("select", item)
    if case == 3:
        control.call("key", "shift", "down")
        control.call("wait", 3)
    control.call("look-at", *aim)
    control.call("wait", 2)
    control.call("mouse", "right", "down")
    control.call("wait", 1)
    control.call("mouse", "right", "up")
    if case == 3:
        control.call("key", "shift", "up")
    control.call("wait", 3)

    state = control.call("block", *target)["state"]
    name = NAMES.get(state.split("[", 1)[0], "none")
    axis = re.search(r"\baxis=([xyz])\b", state)[1] if name != "none" else "none"
    wet = "true" if "waterlogged=true" in state else "false"
    count = control.call("inventory")["counts"].get(item, 0)
    return (str(case), name, axis, wet, str(count))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with (ROOT / "fixtures/shaft-placement-java.csv").open() as stream:
        _, *rows = list(csv.reader(stream))
    with fixture_world(args, "ShaftPlacement", render=True, pack=args.pack) as control:
        control.command("/gamemode survival")
        actual = [place(control, int(row[0])) for row in rows]
    expected = list(map(tuple, rows))
    if actual != expected:
        differences = [f"case {want[0]} Java {want[1:]}, Horizon {got[1:]}"
                       for want, got in zip(expected, actual, strict=True) if want != got]
        raise RuntimeError("Shaft placement mismatch. " + "; ".join(differences))
    print("All ten Java shaft placement and extension cases matched position, axis, water and item use.")


if __name__ == "__main__":
    main()
