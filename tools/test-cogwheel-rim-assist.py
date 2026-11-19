#!/usr/bin/env python3
"""Compare the actual CogwheelBlockItem rim assist with the Java result."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

SMALL = "create:cogwheel"
LARGE = "create:large_cogwheel"


def prepare_encased(control, case, x, y, z):
    item = LARGE if case in (1, 2, 3) else SMALL
    control.commands((
        f"/fill {x - 3} {y - 1} {z - 4} {x + 4} {y - 1} {z + 3} minecraft:smooth_stone",
        f"/fill {x - 2} {y} {z - 2} {x + 3} {y + 3} {z + 2} minecraft:air",
        f"/setblock {x} {y} {z} create:brass_encased_cogwheel[axis=y,top_shaft=false,bottom_shaft=false]",
        f"/item replace entity @s hotbar.0 with {item} 2",
    ))
    if case == 2:
        control.command(f"/setblock {x + 1} {y} {z - 1} minecraft:stone")
    if case == 3:
        control.command(f"/setblock {x + 2} {y} {z - 1} {LARGE}[axis=y]")
    if case == 4:
        feet = (x + 0.5, y, z - 2.1)
        aim = (x + 0.5, y + 0.998, z + 0.5)
    else:
        lane = 0.2 if case in (1, 2, 3) else 0.5
        feet = (x + 2.95, y, z + lane)
        aim = (x + 0.998, y + 0.5, z + lane)
    return item, feet, aim


def prepare_dedicated(control, case, x, y, z):
    mount = LARGE if case in (2, 3) else SMALL
    item = LARGE if case in (1, 3, 6, 7) else SMALL
    control.commands((
        f"/fill {x - 3} {y - 1} {z - 4} {x + 3} {y - 1} {z + 3} minecraft:smooth_stone",
        f"/fill {x - 2} {y} {z - 2} {x + 2} {y + 3} {z + 2} minecraft:air",
        f"/setblock {x} {y} {z} {mount}[axis=y]",
        f"/item replace entity @s hotbar.0 with {item} 2",
    ))
    if case in (6, 7):
        control.command(f"/setblock {x + 1} {y} {z - 1} minecraft:stone")
    if case == 7:
        control.command(f"/setblock {x + 1} {y} {z + 1} minecraft:stone")
    if case in (0, 5):
        feet = (x + 2.7, y, z + 0.5)
        aim = (x + 0.998, y + 0.59, z + 0.5)
    elif case == 4:
        feet = (x + 0.5, y, z - 2.1)
        aim = (x + 0.5, y + 0.998, z + 0.5)
    else:
        feet = (x + 0.85, y, z - 2.15)
        rim = 0.86 if case in (1, 6, 7) else 0.96
        aim = (x + rim, y + 0.62, z + (0.5 if case == 3 else 0.20))
    return item, feet, aim


def place(control, row, *, encased=False):
    case, dx, dy, dz = map(int, row[:4])
    x, y, z = 8 + 5 * case, 101, -10
    prepare = prepare_encased if encased else prepare_dedicated
    item, feet, aim = prepare(control, case, x, y, z)
    control.command("/tp @s " + " ".join(f"{value:.3f}" for value in feet))
    control.call("wait", 3)
    control.call("select", item)
    if case == 5:
        control.call("key", "shift", "down")
        control.call("wait", 3)
    control.call("look-at", *aim)
    control.call("wait", 2)
    hit = control.call("looking-at").get("block")
    if hit is None or hit["pos"] != [x, y, z]:
        raise RuntimeError(f"Case {case} did not aim at the intended gear: {hit}")
    control.call("mouse", "right", "down")
    control.call("wait", 1)
    control.call("mouse", "right", "up")
    if case == 5:
        control.call("key", "shift", "up")
    control.call("wait", 4)

    state = control.call("block", x + dx, y + dy, z + dz)["state"]
    block = state.split("[", 1)[0]
    name = "small" if block == SMALL else "large" if block == LARGE else "none"
    axis = re.search(r"\baxis=([xyz])\b", state)[1] if name != "none" else "none"
    count = control.call("inventory")["counts"].get(item, 0)
    return (name, axis, str(count))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--encased", action="store_true")
    args = parser.parse_args()
    reference = "encased-cogwheel-rim-assist-java.csv" if args.encased else "cogwheel-rim-assist-java.csv"
    world = "EncasedCogwheelRimAssist" if args.encased else "CogwheelRimAssist"
    with (ROOT / "fixtures" / reference).open() as stream:
        _, *rows = list(csv.reader(stream))
    with fixture_world(args, world, render=True, pack=args.pack) as control:
        control.command("/gamemode survival")
        actual = [place(control, row, encased=args.encased) for row in rows]
    expected = [tuple(row[4:7]) for row in rows]
    if actual != expected:
        diffs = [(index, want, got) for index, (want, got) in enumerate(zip(expected, actual, strict=True)) if want != got]
        raise RuntimeError(f"{len(diffs)} cog rim placement differences: {diffs}")
    print(f"All {len(rows)} Java cog rim and fallback cases matched the placed gear, axis and inventory use.")


if __name__ == "__main__":
    main()
