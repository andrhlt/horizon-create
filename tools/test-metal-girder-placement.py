#!/usr/bin/env python3
"""Compare the original Metal Girder placement on every axis and in water."""
import argparse
import csv
from itertools import zip_longest
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

GIRDER = "create:metal_girder"
TARGET = (8, 101, -10)
CASES = (
    ((8, 100, -10), (8.5, 100, -12.5), (8.5, 100.998, -9.5), "up"),
    ((7, 101, -10), (10.65, 101, -9.5), (7.998, 101.68, -9.5), "east"),
    ((8, 101, -11), (8.5, 101, -7.5), (8.5, 101.68, -10.002), "south"),
    ((8, 101, -11), (8.5, 101, -7.5), (8.5, 101.68, -10.002), "south"),
    ((8, 101, -11), (8.5, 101, -7.5), (8.5, 101.68, -10.002), "south"),
)


def coords(position):
    return " ".join(map(str, position))


def setup(control, index):
    support, _, _, _ = CASES[index]
    control.commands((
        "/fill 4 99 -15 15 99 -5 minecraft:smooth_stone",
        "/fill 4 100 -15 15 103 -5 minecraft:air",
        "/gamemode survival",
        f"/setblock {coords(support)} minecraft:stone",
        f"/item replace entity @s hotbar.0 with {GIRDER} 2",
    ))
    if index >= 3:
        level = 0 if index == 3 else 4
        control.command(f"/setblock {coords(TARGET)} minecraft:water[level={level}]")


def place(control, index):
    support, feet, aim, face = CASES[index]
    control.command("/tp @s " + " ".join(f"{value:.3f}" for value in feet))
    control.call("wait", 3)
    control.call("select", GIRDER)
    control.call("look-at", *aim)
    control.call("wait", 2)
    hit = control.call("looking-at").get("block")
    if not hit or hit["pos"] != list(support) or hit["face"] != face:
        raise RuntimeError(f"Case {index} missed the support's {face} face: {hit}")
    control.call("mouse", "right", "down")
    control.call("wait", 1)
    control.call("mouse", "right", "up")
    control.call("wait", 3)


def sample(control, tick, index):
    state = control.call("block", *TARGET)["state"]
    name = state.split("[", 1)[0]
    label = {GIRDER: "girder", "minecraft:air": "air", "minecraft:water": "water"}.get(name, name)
    p = dict(re.findall(r"([a-z_]+)=([a-z]+)", state))
    count = control.call("inventory")["counts"].get(GIRDER, 0)
    return (str(tick), str(index), label, p.get("axis", "none"),
            *(p.get(key, "false") for key in ("x", "z", "top", "bottom", "waterlogged")), str(count))


def verify_shapes(args):
    with fixture_world(args, "GirderShapes", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 4 100 -15 15 100 -5 minecraft:smooth_stone",
            "/fill 4 101 -15 15 104 -5 minecraft:air",
        ))
        states = (
            ("axis=y,x=false,z=false", ((8.1, -9.5, False), (8.5, -9.5, True))),
            ("axis=x,x=true,z=false", ((8.5, -9.9, False), (8.05, -9.5, True))),
            ("axis=z,x=false,z=true", ((8.1, -9.5, False), (8.5, -9.95, True))),
            ("axis=y,x=true,z=true", ((8.1, -9.9, False), (8.20, -9.80, True))),
        )
        for state, rays in states:
            control.command(f"/setblock 8 101 -10 create:metal_girder[{state}]")
            for x, z, want in rays:
                control.command(f"/tp @s {x:.3f} 103.000 {z:.3f}")
                control.call("wait", 2)
                control.call("look-at", x, 100.5, z)
                control.call("wait", 3)
                hit = control.call("looking-at").get("block")
                matches = bool(hit and hit["pos"] == [8, 101, -10])
                if matches != want:
                    raise RuntimeError(f"{state} ray at {(x, z)} expected {want}, got {hit}")
    print("All eight raycasts match the original pole, both beams and cross.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/metal-girder-placement-horizon.csv")
    parser.add_argument("--shapes", action="store_true")
    args = parser.parse_args()
    if args.shapes:
        verify_shapes(args)
        return
    with (ROOT / "fixtures/metal-girder-placement-java.csv").open() as stream:
        header, *expected = list(csv.reader(stream))
    actual = []
    for index in range(len(CASES)):
        with fixture_world(args, f"GirderPlacement{index}", render=True, pack=args.pack) as control:
            setup(control, index)
            start = control.clock()
            for tick in range(1, 9):
                control.step_to(start + tick)
                actual.append(sample(control, tick, index))
                if tick == 3:
                    place(control, index)
    actual.sort(key=lambda row: (int(row[0]), int(row[1])))
    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want, got) for want, got in zip_longest(map(tuple, expected), actual) if want != got]
    if differences:
        raise RuntimeError(f"{len(differences)} differences; first six: {differences[:6]}")
    print(f"Metal Girder placement matched {len(actual)} Java rows on three axes and in source water.")


if __name__ == "__main__":
    main()
