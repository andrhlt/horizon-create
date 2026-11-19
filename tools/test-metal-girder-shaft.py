#!/usr/bin/env python3
"""Replay synchronized Java insertion and removal of a shaft through a Metal Girder."""
import argparse
import csv
from itertools import zip_longest
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

BASE = (8, 101, -10)
GIRDER = "create:metal_girder"
ENCASED = "create:metal_girder_encased_shaft"
SHAFT = "create:shaft"
WRENCH = "create:wrench"


def coords(position):
    return " ".join(map(str, position))


def neighbors(index):
    x, y, z = BASE
    return ((x, y, z - 1), (x, y, z + 1)) if index == 0 else ((x - 1, y, z), (x + 1, y, z))


def setup(control, index):
    source, output = neighbors(index)
    axis, beam, facing = ("z", "x", "south") if index == 0 else ("x", "z", "east")
    control.commands((
        "/fill 4 100 -15 15 100 -5 minecraft:smooth_stone",
        "/fill 4 101 -15 15 103 -5 minecraft:air",
        "/gamemode survival",
        f"/item replace entity @s hotbar.0 with {SHAFT} 2",
        f"/item replace entity @s hotbar.1 with {WRENCH} 1",
        f"/setblock {coords(source)} create:creative_motor[facing={facing}]",
        f"/setblock {coords(output)} {SHAFT}[axis={axis}]",
    ))
    if index == 0:
        control.commands((
            f"/setblock 8 102 -10 {GIRDER}[axis=y,top=true,bottom=true]",
            f"/setblock 8 100 -10 {GIRDER}[axis=y,top=true,bottom=true]",
        ))
    wet = str(index == 0).lower()
    properties = f"axis={beam},x={str(beam == 'x').lower()},z={str(beam == 'z').lower()},top={wet},bottom={wet},waterlogged={wet}"
    control.commands((
        f"/setblock {coords(BASE)} {GIRDER}[{properties}]",
        f"/data merge block {coords(source)} {{ScrollValue:32}}",
    ))


def interact(control, index, inserting, *, teleport=None):
    x, y, z = BASE
    if index == 0:
        feet = (x - 2.35, y, z + 0.5)
        aim = (x + 0.002, y + 0.60, z + 0.5)
        face = "west"
    else:
        feet = (x + 0.5, y, z - 2.5)
        aim = (x + 0.5, y + 0.925, z + 0.5)
        face = "up"
    if teleport is None:
        control.command("/tp @s " + " ".join(f"{value:.3f}" for value in feet))
    else:
        teleport(feet)
    control.call("wait", 3)
    control.call("select", SHAFT if inserting else WRENCH)
    control.call("look-at", *aim)
    control.call("wait", 2)
    hit = control.call("looking-at").get("block")
    if not hit or hit["pos"] != list(BASE) or hit["face"] != face:
        raise RuntimeError(f"Variant {index} missed the girder's {face} face: {hit}")
    control.call("mouse", "right", "down")
    control.call("wait", 1)
    control.call("mouse", "right", "up")
    control.call("wait", 4)


def sample(control, tick, index):
    _, output = neighbors(index)
    stored = control.call("block", *BASE)["state"]
    name = stored.split("[", 1)[0]
    kind = "encased" if name == ENCASED else "girder" if name == GIRDER else "other"
    props = dict(re.findall(r"([a-z_]+)=([a-z]+)", stored))
    count = control.call("inventory")["counts"].get(SHAFT, 0)
    nbt = control.commands(f"/data get block {coords(pos)} Speed" for pos in (BASE, output))
    rpms = [next(iter(re.findall(r"(-?\d+\.\d+)f\b", message)), "0.0") for message in nbt]
    return (str(tick), str(index), kind, props.get("axis", "none"),
            *(props.get(property, "false") for property in ("x", "z", "top", "bottom", "waterlogged")),
            str(count), *(f"{float(value):.4f}" for value in rpms))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/metal-girder-shaft-horizon.csv")
    args = parser.parse_args()
    with (ROOT / "fixtures/metal-girder-shaft-java.csv").open() as stream:
        header, *expected = list(csv.reader(stream))
    actual = []
    for index in range(2):
        with fixture_world(args, f"MetalGirderShaft{index}", render=True, pack=args.pack) as control:
            setup(control, index)
            start = control.clock()
            for tick in range(1, 13):
                control.step_to(start + tick)
                row = sample(control, tick, index)
                actual.append(row)
                if tick == 3 or (tick == 8 and row[2] == "encased"):
                    interact(control, index, tick == 3)
    actual.sort(key=lambda row: (int(row[0]), int(row[1])))
    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want, got) for want, got in zip_longest(map(tuple, expected), actual) if want != got]
    if differences:
        raise RuntimeError(f"{len(differences)} differences; first six: {differences[:6]}")
    print(f"Metal Girder shaft insertion, axis, waterlogging, inventory and output matched {len(actual)} Java rows.")


if __name__ == "__main__":
    main()
