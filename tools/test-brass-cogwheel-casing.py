#!/usr/bin/env python3
"""Compare Brass Encased Cogwheel conversion, wrench ends, and output power."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

BASE = (8, 101, -10)
AXIAL_OUT = (9, 101, -10)
CASING = "create:brass_casing"
CASE = "create:brass_encased_cogwheel"
WRENCH = "create:wrench"


def coords(pos):
    return " ".join(map(str, pos))


def setup(control):
    control.commands((
        "/fill 4 100 -15 15 100 -7 minecraft:smooth_stone",
        "/fill 4 101 -15 15 103 -7 minecraft:air",
        "/setblock 7 101 -10 create:creative_motor[facing=east]",
        f"/setblock {coords(BASE)} create:cogwheel[axis=x]",
        f"/setblock {coords(AXIAL_OUT)} create:shaft[axis=x]",
        "/data merge block 7 101 -10 {ScrollValue:24}",
        "/gamemode survival",
        f"/item replace entity @s hotbar.0 with {CASING} 2",
        f"/item replace entity @s hotbar.1 with {WRENCH} 1",
    ))


def act(control, tick, *, teleport=True):
    x, y, z = BASE
    if tick in (6, 8, 10):
        feet = (x + 2.65, y, z + 0.5)
        aim = (x + 0.998, y + 0.79, z + 0.5)
        face = "east"
    else:
        feet = (x + 0.5, y, z - 2.5)
        if tick == 3:
            aim = (x + 0.5, y + 0.865, z + 0.5)
            face = "up"
        elif tick == 12:
            aim = (x + 0.5, y + 0.45, z + 0.002)
            face = "north"
        else:
            aim = (x + 0.5, y + 0.998, z + 0.5)
            face = "up"
    if teleport:
        control.command("/tp @s " + " ".join(f"{value:.3f}" for value in feet))
        control.call("wait", 3)
    control.call("select", CASING if tick == 3 else WRENCH)
    if tick == 14:
        control.call("key", "shift", "down")
        control.call("wait", 3)
    control.call("look-at", *aim)
    control.call("wait", 2)
    hit = control.call("looking-at").get("block")
    if not hit or hit["pos"] != list(BASE) or hit["face"] != face:
        raise RuntimeError(f"Tick {tick} missed the intended cog's {face} face: {hit}")
    control.call("mouse", "right", "down")
    control.call("wait", 1)
    control.call("mouse", "right", "up")
    if tick == 14:
        control.call("key", "shift", "up")
    control.call("wait", 4)


def sample(control, tick):
    state = control.call("block", *BASE)["state"]
    kind = state.split("[", 1)[0]
    properties = dict(re.findall(r'([a-z_]+)=([a-z]+)', state))
    label = "encased" if kind == CASE else "cog" if kind == "create:cogwheel" else "none"
    count = control.call("inventory")["counts"].get(CASING, 0)
    nbt = control.commands(f"/data get block {coords(pos)} Speed" for pos in (BASE, AXIAL_OUT))
    speeds = [next(iter(re.findall(r"(-?\d+\.\d+)f\b", message)), "0.0") for message in nbt]
    return (str(tick), label, properties.get("axis", "none"), properties.get("top_shaft", "false"),
            properties.get("bottom_shaft", "false"), str(count), *(f"{float(speed):.4f}" for speed in speeds))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/brass-cogwheel-casing-horizon.csv")
    args = parser.parse_args()
    with (ROOT / "fixtures/brass-cogwheel-casing-java.csv").open() as stream:
        header, _, *rows = list(csv.reader(stream))

    actual = []
    with fixture_world(args, "BrassCogwheelCasing", render=True, pack=args.pack) as control:
        setup(control)
        start = control.clock()
        for row in rows:
            tick = int(row[0])
            control.step_to(start + tick)
            got = sample(control, tick)
            actual.append(got)
            if tick in (3, 6, 8, 10, 12, 14):
                if tick > 3 and got[1] != "encased":
                    break
                act(control, tick)
    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    expected = list(map(tuple, rows))
    if actual != expected:
        differences = [(want, got) for want, got in zip(expected, actual) if want != got]
        raise RuntimeError(f"{len(differences)} differences across {len(actual)} sampled ticks. First six: {differences[:6]}")
    print(f"Brass casing, shaft-end toggles, side turn, and wrench removal matched Java for {len(actual)} simulated ticks.")


if __name__ == "__main__":
    main()
