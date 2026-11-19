#!/usr/bin/env python3
"""Replay the other three Java encased cogwheel material and size combinations."""
import argparse
import csv
from itertools import zip_longest
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

VARIANTS = (
    ("create:cogwheel", "create:andesite_casing", "create:andesite_encased_cogwheel"),
    ("create:large_cogwheel", "create:andesite_casing", "create:andesite_encased_large_cogwheel"),
    ("create:large_cogwheel", "create:brass_casing", "create:brass_encased_large_cogwheel"),
)
WRENCH = "create:wrench"


def coords(pos):
    return " ".join(map(str, pos))


def positions(index):
    z = -10 + index * 5
    return (8, 101, z), (9, 101, z), (8, 101 + int(index > 0), z + 1)


def setup(control):
    control.commands((
        "/fill 4 100 -15 15 100 4 minecraft:smooth_stone",
        "/fill 4 101 -15 15 103 4 minecraft:air",
        "/gamemode survival",
        f"/item replace entity @s hotbar.3 with {WRENCH} 1",
    ))
    for index, (bare, casing, _) in enumerate(VARIANTS):
        pos, output, gear = positions(index)
        x, y, z = pos
        control.commands((
            f"/setblock {x - 1} {y} {z} create:creative_motor[facing=east]",
            f"/setblock {coords(pos)} {bare}[axis=x]",
            f"/setblock {coords(output)} create:shaft[axis=x]",
            f"/setblock {coords(gear)} create:cogwheel[axis=x]",
            f"/data merge block {x - 1} {y} {z} {{ScrollValue:24}}",
        ))
    control.commands((
        "/item replace entity @s hotbar.0 with create:andesite_casing 2",
        "/item replace entity @s hotbar.1 with create:brass_casing 2",
    ))


def interact(control, tick, index, *, teleport=None):
    x, y, z = positions(index)[0]
    if tick == 6:
        feet = (x + 2.65, y, z + 0.5)
        aim = (x + 0.998, y + 0.79, z + 0.5)
        face = "east"
    else:
        feet = (x + 0.5, y, z - 2.5)
        aim_y = y + (0.865 if tick == 3 and index == 0 else 0.978)
        aim = (x + 0.5, aim_y, z + 0.5)
        face = "up"
    if teleport is None:
        control.command("/tp @s " + " ".join(f"{value:.3f}" for value in feet))
    else:
        teleport(feet)
    control.call("wait", 3)
    control.call("select", VARIANTS[index][1] if tick == 3 else WRENCH)
    if tick == 10:
        control.call("key", "shift", "down")
        control.call("wait", 3)
    control.call("look-at", *aim)
    control.call("wait", 2)
    hit = control.call("looking-at").get("block")
    if not hit or hit["pos"] != [x, y, z] or hit["face"] != face:
        raise RuntimeError(f"Tick {tick}, variant {index}, missed its {face} face: {hit}")
    control.call("mouse", "right", "down")
    control.call("wait", 1)
    control.call("mouse", "right", "up")
    if tick == 10:
        control.call("key", "shift", "up")
    control.call("wait", 4)


def sample(control, tick, index):
    pos, output, gear = positions(index)
    bare, casing, expected = VARIANTS[index]
    stored = control.call("block", *pos)["state"]
    name = stored.split("[", 1)[0]
    kind = "encased" if name == expected else "bare" if name == bare else "unexpected"
    props = dict(re.findall(r"([a-z_]+)=([a-z]+)", stored))
    count = control.call("inventory")["counts"].get(casing, 0)
    nbt = control.commands(f"/data get block {coords(pos)} Speed" for pos in (pos, output, gear))
    rpms = [next(iter(re.findall(r"(-?\d+\.\d+)f\b", message)), "0.0") for message in nbt]
    return (str(tick), str(index), kind, props.get("axis", "none"), props.get("top_shaft", "false"),
            props.get("bottom_shaft", "false"), str(count), *(f"{float(value):.4f}" for value in rpms))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/encased-cogwheel-family-horizon.csv")
    args = parser.parse_args()
    with (ROOT / "fixtures/encased-cogwheel-family-java.csv").open() as stream:
        header, *expected = list(csv.reader(stream))
    actual = []
    with fixture_world(args, "EncasedCogwheelFamily", render=True, pack=args.pack) as control:
        setup(control)
        start = control.clock()
        for tick in range(1, 15):
            control.step_to(start + tick)
            for index in range(len(VARIANTS)):
                row = sample(control, tick, index)
                actual.append(row)
                if tick == 3 or (tick in (6, 10) and row[2] == "encased"):
                    interact(control, tick, index)
    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want, got) for want, got in zip_longest(map(tuple, expected), actual) if want != got]
    if differences:
        raise RuntimeError(f"{len(differences)} mismatches; first six: {differences[:6]}")
    print(f"All three remaining Java encased cogwheel variants matched {len(actual)} sampled rows.")


if __name__ == "__main__":
    main()
