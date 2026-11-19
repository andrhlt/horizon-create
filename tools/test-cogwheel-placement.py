#!/usr/bin/env python3
"""Compare normal small and large cogwheel placement against Java."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

COG = {"create:cogwheel": "small", "create:large_cogwheel": "large"}
FACE = {"west": (-1, 0, 0), "north": (0, 0, -1), "up": (0, 1, 0)}
ITEMS = {index: "create:large_cogwheel" if index in (1, 3, 5, 7, 8) else "create:cogwheel"
         for index in range(10)}


def coords(pos):
    return " ".join(map(str, pos))


def setup(control, case):
    x, y, z = target = (8 + case % 5 * 4, 101, -10 + case // 5 * 6)
    item = ITEMS[case]
    face = "west" if case in (0, 4, 5, 7, 8) else "north" if case == 1 else "up"
    support = tuple(value - movement for value, movement in zip(target, FACE[face], strict=True))
    support_block = "create:cogwheel[axis=y]" if case in (4, 5) else "minecraft:stone"
    control.commands((
        f"/fill {x - 2} {y - 1} {z - 2} {x + 2} {y - 1} {z + 2} minecraft:smooth_stone",
        f"/fill {x - 2} {y} {z - 2} {x + 2} {y + 1} {z + 2} minecraft:air",
        f"/setblock {coords(support)} {support_block}",
        f"/tp @s {x - 1.7} {y} {z - 1.25}",
        f"/item replace entity @s hotbar.0 with {item} 2",
    ))
    if case == 5:
        # Force the direct placement path used by the Java ordinary fixture.
        # Both rim-assisted diagonals are obstructed.
        control.commands((
            f"/setblock {x} {y} {z - 1} minecraft:stone",
            f"/setblock {x} {y} {z + 1} minecraft:stone",
            f"/tp @s {x - 1.7:.3f} {y} {z + 0.5}",
        ))
    if case in (2, 9):
        control.command(f"/setblock {x - 1} {y} {z} create:shaft[axis=x]")
    if case in (3, 9):
        control.command(f"/setblock {x} {y} {z - 1} create:shaft[axis=z]")
    if case == 6:
        control.command(f"/setblock {x + 1} {y} {z} create:large_cogwheel[axis=y]")
    if case in (7, 8):
        control.command(f"/setblock {x} {y} {z} minecraft:water[level={0 if case == 7 else 1}]")
    return (target, support, face, item)


def place(control, case):
    target, support, face, item = setup(control, case)
    control.call("wait", 3)
    control.call("select", item)
    if case == 3:
        control.call("key", "shift", "down")
        control.call("wait", 3)
    try:
        control.call("interact", *support, face)
    finally:
        if case == 3:
            control.call("key", "shift", "up")
    control.call("wait", 2)

    state = control.call("block", *target)["state"]
    cog = COG.get(state.split("[", 1)[0], "none")
    axis = re.search(r"\baxis=([xyz])\b", state)[1] if cog != "none" else "none"
    wet = cog != "none" and "waterlogged=true" in state
    count = control.call("inventory")["counts"].get(item, 0)
    return (str(case), cog, axis, "true" if wet else "false", str(count))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with (ROOT / "fixtures/cogwheel-placement-java.csv").open() as stream:
        _, *rows = list(csv.reader(stream))
    with fixture_world(args, "CogwheelPlacement", render=True, pack=args.pack) as control:
        control.command("/gamemode survival")
        actual = [place(control, int(row[0])) for row in rows]
    expected = list(map(tuple, rows))
    if actual != expected:
        differences = [f"case {want[0]} Java {want[1:]}, Horizon {got[1:]}"
                       for want, got in zip(expected, actual, strict=True) if want != got]
        raise RuntimeError("Cog placement mismatch. " + "; ".join(differences))
    print("All ten Java cog placement cases matched for orientation, waterlogging, and held item use.")


if __name__ == "__main__":
    main()
