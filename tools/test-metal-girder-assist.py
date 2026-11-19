#!/usr/bin/env python3
"""Compare the original Metal Girder line placement helper."""
import argparse
import csv
from itertools import zip_longest
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

GIRDER = "create:metal_girder"
ORIGIN = (8, 101, -20)


def pos(values):
    return " ".join(map(str, values))


def setup(control, index):
    x, y, z = ORIGIN
    vertical = index == 1
    axis = "y" if vertical else "x"
    is_x = str(not vertical).lower()
    is_vertical = str(vertical).lower()
    state = f"{GIRDER}[axis={axis},x={is_x},top={is_vertical},bottom={is_vertical}]"
    control.commands((
        "/fill 4 100 -25 23 100 -16 minecraft:smooth_stone",
        "/fill 4 101 -25 23 105 -16 minecraft:air",
        "/gamemode survival",
        f"/item replace entity @s hotbar.0 with {GIRDER} 2",
        f"/setblock {pos(ORIGIN)} {state}",
    ))
    if index == 2:
        control.command(f"/setblock {x + 1} {y} {z} minecraft:stone")
    else:
        for distance in range(1, 13 if index == 3 else 2):
            target = (x, y + distance, z) if vertical else (x + distance, y, z)
            control.command(f"/setblock {pos(target)} {state}")
    if index == 4:
        control.command(f"/setblock {x + 2} {y} {z} minecraft:water")


def place(control, index, *, teleport=None):
    x, y, z = ORIGIN
    if index == 1:
        feet, aim, face = (x - 2.35, y, z + 0.5), (x + 0.251, y + 0.88, z + 0.5), "west"
    else:
        feet, aim, face = (x + 0.88, y, z - 2.5), (x + 0.88, y + 0.873, z + 0.5), "up"
    if teleport is None:
        control.command("/tp @s " + " ".join(f"{value:.3f}" for value in feet))
    else:
        teleport(feet)
    control.call("wait", 3)
    control.call("select", GIRDER)
    control.call("look-at", *aim)
    control.call("wait", 2)
    hit = control.call("looking-at").get("block")
    if not hit or hit["pos"] != list(ORIGIN) or hit["face"] != face:
        raise RuntimeError(f"Case {index} missed the girder's {face} face: {hit}")
    control.call("mouse", "right", "down")
    control.call("wait", 1)
    control.call("mouse", "right", "up")
    control.call("wait", 3)


def target(index):
    x, y, z = ORIGIN
    if index == 1:
        return x, y + 2, z
    return (x - 1 if index in (2, 3) else x + 2), y, z


def sample(control, tick, index):
    state = control.call("block", *target(index))["state"]
    name = state.split("[", 1)[0]
    label = {GIRDER: "girder", "minecraft:air": "air", "minecraft:water": "water"}.get(name, name)
    prop = dict(re.findall(r"([a-z_]+)=([a-z]+)", state))
    count = control.call("inventory")["counts"].get(GIRDER, 0)
    return (str(tick), str(index), label, prop.get("axis", "none"),
            *(prop.get(key, "false") for key in ("x", "z", "top", "bottom", "waterlogged")), str(count))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/metal-girder-assist-horizon.csv")
    args = parser.parse_args()
    with (ROOT / "fixtures/metal-girder-assist-java.csv").open() as stream:
        header, *expected = list(csv.reader(stream))
    actual = []
    for index in range(5):
        with fixture_world(args, f"GirderAssist{index}", render=True, pack=args.pack) as control:
            setup(control, index)
            start = control.clock()
            for tick in range(1, 8):
                control.step_to(start + tick)
                actual.append(sample(control, tick, index))
                if tick == 3:
                    place(control, index)
            x, y, z = ORIGIN
            ordinary = (x - 1, y, z) if index == 1 else (x, y + 1, z)
            state = control.call("block", *ordinary)["state"]
            if state != "minecraft:air":
                raise RuntimeError(f"Case {index} placed an extra block at {ordinary}: {state}")
    actual.sort(key=lambda row: (int(row[0]), int(row[1])))
    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want, got) for want, got in zip_longest(map(tuple, expected), actual) if want != got]
    if differences:
        raise RuntimeError(f"{len(differences)} differences; first six: {differences[:6]}")
    print(f"Metal Girder placement assistance matched {len(actual)} Java rows.")


if __name__ == "__main__":
    main()
