#!/usr/bin/env python3
"""Compare Java's vertical Depot input and first powered Press cycle."""
import argparse
import csv
from importlib import import_module
import os
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

depot = import_module("test-depot-pressing")
multiplayer = import_module("test-multiplayer")
DEPOT = "5 105 -11"
PRESS = "5 107 -11"
INGOT = "minecraft:iron_ingot"
SHEET = "create:iron_sheet"
FALLING = (
    '@e[type=minecraft:item,x=4,y=104,z=-12,dx=3,dy=5,dz=3,limit=1,'
    'nbt={Item:{id:"minecraft:iron_ingot"}}]'
)


def setup(control):
    control.commands((
        "/fill 3 104 -13 10 104 -8 minecraft:smooth_stone",
        "/gamemode spectator",
        "/tp @s 8.5 106 -10.5",
        f"/setblock {DEPOT} create:depot",
        f"/setblock {PRESS} create:mechanical_press[facing=east]",
        "/setblock 4 107 -11 create:creative_motor[facing=east]{ScrollValue:128}",
    ))
    for _ in range(5):
        control.step_to(control.clock() + 1)
    control.command('/summon minecraft:item 5.5 106.875 -10.5 '
                    '{Item:{id:"minecraft:iron_ingot",count:1},PickupDelay:32767s,Motion:[0.0d,0.0d,0.0d]}')


def number(reply):
    match = re.search(r"(-?\d+(?:\.\d+)?)[df]?$", reply)
    return float(match[1]) if match else None


def cues(control):
    marker = "CREATE_ELEVATOR_PLAYBACK "
    lines = (control.socket.parent / "ctl.log").read_text().splitlines()
    results = []
    for line in lines:
        if marker not in line:
            continue
        sound, source, x, y, z, volume, pitch = line.split(marker, 1)[1].split(",")
        if sound != "create:depot_plop":
            continue
        if tuple(map(float, (x, y, z))) != (5.5, 105.5, -10.5):
            raise RuntimeError(f"Wrong Depot drop sound position: {line}")
        category = "block" if source == "4" else source
        results.append(f"{sound}/{category}/{float(volume):.6f}/{float(pitch):.6f}")
    return results


def run(args):
    with args.reference.open() as text:
        rows = csv.reader(text)
        header, expected = next(rows), list(rows)
    actual = []
    heard = 0
    if args.sound:
        os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    with fixture_world(args, "DepotDropPress", render=args.sound, pack=args.pack) as control:
        setup(control)
        start = control.clock()
        for index, row in enumerate(expected):
            if index:
                control.step_to(start + index)
            falling, items, position, press = control.commands((
                f"/data get entity {FALLING} Pos[1]", f"/data get block {DEPOT} Items",
                f"/data get block {DEPOT} BeltPosition", f"/data get block {PRESS}",
            ))
            y = number(falling)
            observe = [
                str(index), str(int(y is not None)), f"{y - 105 if y is not None else -1:.6f}",
                str(int(INGOT in items)), str(int(SHEET in items)), f"{number(position) or 0:.6f}",
                str(depot.scalar(press, "Ticks")),
            ]
            events = []
            if args.sound:
                if row[-1] != "-":
                    count = len(row[-1].split(";"))
                    multiplayer.until(f"the Depot's plop cue at tick {index}",
                                      lambda: len(cues(control)) >= heard + count)
                sounds = cues(control)
                events = sounds[heard:]
                heard = len(sounds)
                if control.clock() != start + index:
                    raise RuntimeError("Sound capture moved the simulation forward.")
            actual.append(observe + [";".join(events) or "-"])
    if args.trace:
        with args.trace.open("w") as text:
            writer = csv.writer(text, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(actual)
    differences = [
        (want, got) for want, got in zip(expected, actual, strict=True)
        if want[:2] != got[:2] or abs(float(want[2]) - float(got[2])) > .000002
        or want[3:7] != got[3:7] or (args.sound and want[-1] != got[-1])
    ]
    if differences:
        raise RuntimeError(f"Depot drop differs on {len(differences)} Java rows. First: {differences[:9]}")
    print(f"Vertical Depot drop and powered pressing matched {len(actual)} original Java ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/depot-drop-press-java.csv")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--sound", action="store_true")
    run(parser.parse_args())
