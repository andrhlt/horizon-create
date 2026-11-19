#!/usr/bin/env python3
"""Compare the original plain Metal Girder wrench toggles."""
import argparse
import csv
from itertools import zip_longest
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

GIRDER = "create:metal_girder"
WRENCH = "create:wrench"
BASE = (8, 101, -10)


def setup(control, index):
    control.commands((
        "/fill 4 100 -15 14 100 -5 minecraft:smooth_stone",
        "/fill 4 101 -15 14 104 -5 minecraft:air",
        "/gamemode survival",
        f"/item replace entity @s hotbar.0 with {WRENCH} 1",
    ))
    axis = "y" if index == 3 else "x"
    z = str(index == 2).lower()
    top = str(index in (1, 3)).lower()
    bottom = str(index == 3).lower()
    control.command(f"/setblock 8 101 -10 {GIRDER}[axis={axis},x=true,z={z},top={top},bottom={bottom}] strict")
    if index == 1:
        control.command(f"/setblock 8 102 -10 {GIRDER}[axis=x,x=true,bottom=true] strict")


def turn(control, index, *, lower=False, teleport=None):
    x, y, z = BASE
    feet = (x + 0.5, y, z - 2.5)
    aim_y = y + (0.17 if lower else 0.80)
    aim_z = z + (0.001 if index == 2 else 0.251)
    if teleport is None:
        control.command("/tp @s " + " ".join(f"{value:.3f}" for value in feet))
    else:
        teleport(feet)
    control.call("wait", 3)
    control.call("select", WRENCH)
    control.call("look-at", x + 0.5, aim_y, aim_z)
    control.call("wait", 2)
    hit = control.call("looking-at").get("block")
    if not hit or hit["pos"] != list(BASE) or hit["face"] != "north":
        raise RuntimeError(f"Girder case {index} missed its north {'lower' if lower else 'upper'} edge: {hit}")
    control.call("mouse", "right", "down")
    control.call("wait", 1)
    control.call("mouse", "right", "up")
    control.call("wait", 3)


def sample(control, tick, index):
    center = control.call("block", *BASE)["state"]
    x, y, z = BASE
    upper = control.call("block", x, y + 1, z)["state"]
    if not center.startswith(GIRDER + "["):
        raise RuntimeError(f"Tick {tick}, case {index}: main girder disappeared: {center}")
    p = dict(re.findall(r"([a-z_]+)=([a-z]+)", center))
    upper_bottom = "true" if upper.startswith(GIRDER + "[") and "bottom=true" in upper else "false"
    return (str(tick), str(index), p["axis"], *(p.get(key, "false") for key in ("x", "z", "top", "bottom")), upper_bottom)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/metal-girder-wrench-horizon.csv")
    args = parser.parse_args()
    with (ROOT / "fixtures/metal-girder-wrench-java.csv").open() as stream:
        header, *expected = list(csv.reader(stream))
    actual = []
    for index in range(4):
        with fixture_world(args, f"GirderWrench{index}", render=True, pack=args.pack) as control:
            setup(control, index)
            start = control.clock()
            for tick in range(1, 10):
                control.step_to(start + tick)
                actual.append(sample(control, tick, index))
                if tick == 3 or (tick == 5 and index == 0) or (tick == 7 and index < 2):
                    turn(control, index, lower=tick == 5)
    actual.sort(key=lambda row: (int(row[0]), int(row[1])))
    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want, got) for want, got in zip_longest(map(tuple, expected), actual) if want != got]
    if differences:
        raise RuntimeError(f"{len(differences)} differences; first six: {differences[:6]}")
    print(f"Plain girder wrench matched {len(actual)} Java rows for single, paired, cross and axis cases.")


if __name__ == "__main__":
    main()
