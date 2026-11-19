#!/usr/bin/env python3
"""Compare Java crouch pickup and ordinary drops for an encased girder shaft."""
import argparse
import csv
import importlib.util
from itertools import zip_longest
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

path = ROOT / "tools/test-metal-girder-shaft.py"
spec = importlib.util.spec_from_file_location(path.stem, path)
shaft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shaft)


def setup(control, index):
    shaft.setup(control, 1)
    wet = str(index == 1).lower()
    control.commands((
        "/item replace entity @s hotbar.0 with minecraft:air",
        f"/setblock {shaft.coords(shaft.BASE)} {shaft.ENCASED}[axis=x,waterlogged={wet}]",
    "/tp @s 11.500 101 -9.500",
    ))


def pickup(control, *, teleport=None):
    x, y, z = shaft.BASE
    feet = (x + 0.5, y, z - 2.5)
    if teleport is None:
        control.command("/tp @s " + " ".join(f"{value:.3f}" for value in feet))
    else:
        teleport(feet)
    control.call("wait", 3)
    control.call("select", shaft.WRENCH)
    control.call("key", "shift", "down")
    control.call("wait", 3)
    control.call("look-at", x + 0.5, y + 0.82, z + 0.5)
    control.call("wait", 2)
    hit = control.call("looking-at").get("block")
    if not hit or hit["pos"] != list(shaft.BASE) or hit["face"] != "up":
        raise RuntimeError(f"Crouch wrench missed the encased girder's up face: {hit}")
    control.call("mouse", "right", "down")
    control.call("wait", 1)
    control.call("mouse", "right", "up")
    control.call("key", "shift", "up")
    control.call("wait", 4)


def sample(control, tick, index):
    output = shaft.neighbors(1)[1]
    stored = control.call("block", *shaft.BASE)["state"].split("[", 1)[0]
    names = {shaft.ENCASED: "encased", "minecraft:air": "air", "minecraft:water": "water"}
    counts = control.call("inventory")["counts"]
    dropped = control.call("entities", 12, "minecraft:item")["entities"]
    rpm = control.command(f"/data get block {shaft.coords(output)} Speed")
    speed = float(next(iter(re.findall(r"(-?\d+\.\d+)f\b", rpm)), "0.0"))
    loot = [sum(entity["item"]["count"] for entity in dropped if entity["item"]["item"] == name)
            for name in (shaft.GIRDER, shaft.SHAFT)]
    return (str(tick), str(index), names.get(stored, stored), str(counts.get(shaft.GIRDER, 0)),
            str(counts.get(shaft.SHAFT, 0)), *(str(count) for count in loot), f"{speed:.4f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/metal-girder-pickup-horizon.csv")
    args = parser.parse_args()
    with (ROOT / "fixtures/metal-girder-pickup-java.csv").open() as stream:
        header, *expected = list(csv.reader(stream))
    actual = []
    for index in range(3):
        with fixture_world(args, f"MetalGirderPickup{index}", render=True, pack=args.pack) as control:
            setup(control, index)
            start = control.clock()
            for tick in range(1, 9):
                control.step_to(start + tick)
                actual.append(sample(control, tick, index))
                if tick == 3:
                    if index == 2:
                        control.command(f"/setblock {shaft.coords(shaft.BASE)} minecraft:air destroy")
                    else:
                        pickup(control)
    actual.sort(key=lambda row: (int(row[0]), int(row[1])))
    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want, got) for want, got in zip_longest(map(tuple, expected), actual) if want != got]
    if differences:
        raise RuntimeError(f"{len(differences)} differences; first six: {differences[:6]}")
    print(f"Dry and wet crouch pickup, ordinary break drops, and transmission matched {len(actual)} Java rows.")


if __name__ == "__main__":
    main()
