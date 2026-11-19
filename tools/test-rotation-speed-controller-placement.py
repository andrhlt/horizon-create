#!/usr/bin/env python3
"""Compare survival controller and large-cog placement with Java."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

CONTROLLER = "create:rotation_speed_controller"
LARGE_COG = "create:large_cogwheel"


def axis(control, pos, block):
    state = control.call("block", *pos)["state"]
    if state.split("[", 1)[0] != block:
        return "none"
    return re.search(r"\baxis=([xyz])\b", state)[1]


def place(control, index):
    x, y, z = 8 + 4 * index, 101, -10
    item = LARGE_COG if index < 4 else CONTROLLER
    control.commands((
        f"/fill {x - 2} {y - 1} {z - 2} {x + 1} {y - 1} {z + 2} minecraft:smooth_stone",
        f"/fill {x - 2} {y} {z - 2} {x + 1} {y + 2} {z + 2} minecraft:air",
        f"/tp @s {x - 2} {y} {z + 0.5} {90 if index == 5 else 0} 0",
        f"/item replace entity @s hotbar.0 with {item} 2",
    ))
    if index < 4:
        control.command(f"/setblock {x} {y} {z} {CONTROLLER}[axis={'z' if index == 1 else 'x'}]")
        if index == 2:
            control.command(f"/setblock {x} {y + 1} {z} minecraft:stone")
        if index == 3:
            control.command(f"/setblock {x + 1} {y + 1} {z} create:cogwheel[axis=y]")
    elif index == 4:
        control.command(f"/setblock {x} {y + 1} {z} {LARGE_COG}[axis=x]")
    else:
        control.commands((
            f"/setblock {x + 1} {y} {z} create:shaft[axis=x]",
            f"/setblock {x} {y + 1} {z} create:shaft[axis=y]",
        ))

    control.call("wait", 3)
    control.call("select", item)
    if index < 4:
        control.call("look-at", x + 0.01, y + 0.2, z + 0.5)
        control.call("mouse", "right", "down")
        control.call("wait", 1)
        control.call("mouse", "right", "up")
    else:
        control.call("interact", x, y - 1, z, "up")
    control.call("wait", 2)
    return (
        str(index),
        axis(control, (x, y, z), CONTROLLER),
        axis(control, (x, y + 1, z), LARGE_COG),
        axis(control, (x - 1, y, z), LARGE_COG),
        str(control.call("inventory")["counts"].get(item, 0)),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()

    with (ROOT / "fixtures/rotation-speed-controller-placement-java.csv").open() as stream:
        _, *rows = list(csv.reader(stream))
    with fixture_world(args, "rotation-speed-controller-placement", render=True, pack=args.pack) as control:
        control.command("/gamemode survival")
        actual = [place(control, int(row[0])) for row in rows]
    expected = list(map(tuple, rows))
    if actual != expected:
        differences = [f"case {wanted[0]} expected {wanted[1:]}, got {got[1:]}"
                       for wanted, got in zip(expected, actual, strict=True) if wanted != got]
        raise RuntimeError("Controller placement mismatch. " + "; ".join(differences))
    print("Both cog helper axes, blocked fallback placement, and controller orientation matched Java in all six cases.")


if __name__ == "__main__":
    main()
