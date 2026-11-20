#!/usr/bin/env python3
"""Replay Java Create's Press over three dropped iron ingots."""
import argparse
import csv
import os
from importlib import import_module
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

depot = import_module("test-depot-pressing")
multiplayer = import_module("test-multiplayer")
PRESS = "8 180 8"
SOUND_AT = (8.5, 180.5, 8.5)
TRACE = "CREATE_ELEVATOR_PLAYBACK "
CUES = ("create:mechanical_press_activation", "create:mechanical_press_activation_compounded_1")


def setup(control):
    control.commands((
        "/fill 6 178 6 10 178 10 minecraft:stone",
        "/gamemode spectator",

        "/tp @s 8.5 181 11.5",
        "/setblock 8 180 7 create:creative_motor[facing=south]{ScrollValue:128}",
        f"/setblock {PRESS} create:mechanical_press[facing=south]",
    ))
    for _ in range(5):
        control.step_to(control.clock() + 1)
    control.command('/summon minecraft:item 8.5 179.875 8.5 {Item:{id:"minecraft:cobblestone",count:1},'
                    'PickupDelay:32767s,Motion:[0.0d,0.0d,0.0d]}')
    control.command('/summon minecraft:item 8.5 179.875 8.5 {Item:{id:"minecraft:iron_ingot",count:3},'
                    'PickupDelay:32767s,Motion:[0.0d,0.0d,0.0d]}')


def target(item):
    return ('@e[type=minecraft:item,x=7.75,y=178.75,z=7.75,dx=1.5,dy=1.5,dz=1.5,'
            f'nbt={{Item:{{id:"{item}"}}}},limit=1]')


def count(reply):
    match = re.search(r'\bcount: (\d+)', reply)
    return int(match[1]) if match else 0


def playback(control):
    events = []
    for line in (control.socket.parent / "ctl.log").read_text().splitlines():
        if TRACE not in line:
            continue
        identifier, source, x, y, z, volume, pitch = line.split(TRACE, 1)[1].split(",")
        if identifier not in CUES:
            continue
        if source not in ("4", "block") or tuple(map(float, (x, y, z))) != SOUND_AT:
            raise RuntimeError(f"Unexpected press sound position or category: {line}")
        events.append(f"{identifier}/{float(volume):.6f}/{float(pitch):.6f}")
    return events


def run(args):
    with args.reference.open() as text:
        rows = csv.reader(text)
        header, expected = next(rows), list(rows)
    actual = []
    if args.sound:
        os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    ingots = target("minecraft:iron_ingot")
    sheets = target("create:iron_sheet")
    invalid = target("minecraft:cobblestone")
    with fixture_world(args, "GroundItemPress", render=args.sound, pack=args.pack) as control:
        setup(control)
        start = control.clock()
        delivered = 0
        heard = 0
        for tick, expected_row in enumerate(expected):
            if tick:
                control.step_to(start + tick)
            press, iron, ground, output = control.commands((
                f"/data get block {PRESS}", f"/data get entity {ingots} Item",
                f"/data get entity {ingots} OnGround", f"/data get entity {sheets} Item",
            ))
            if "create:mechanical_press" not in press:
                raise RuntimeError("Press is missing from the rig")
            if extracted := count(output):
                delivered += extracted
                control.command(f"/kill {sheets}")
            invalid_stack = control.command(f"/data get entity {invalid} Item")
            if "minecraft:cobblestone" not in invalid_stack or count(invalid_stack) != 1:
                raise RuntimeError(f"A cobblestone without a pressing recipe was consumed or converted: {invalid_stack}")
            grounded = int(ground.endswith("1b"))
            offset = depot.head_offset(press) * (16 / 19)
            events = []
            if args.sound:
                if expected_row[-1] != "-":
                    expected_sound_count = len(expected_row[-1].split(";"))
                    multiplayer.until(f"ground press impact at tick {tick}",
                                      lambda: len(playback(control)) >= heard + expected_sound_count)
                sounds = playback(control)
                events = sounds[heard:]
                heard = len(sounds)
                if control.clock() != start + tick:
                    raise RuntimeError("Sound poll advanced the simulation tick.")
            actual.append([
                str(tick), *(str(depot.scalar(press, key)) for key in
                             ("Speed", "Running", "Finished", "Mode", "Ticks")),
                f"{offset:.6f}", str(count(iron)), str(grounded), str(delivered),
                ";".join(events) or "-",
            ])
    if args.trace:
        with args.trace.open("w") as text:
            writer = csv.writer(text, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(actual)
    mismatches = [
        (want, got) for want, got in zip(expected, actual, strict=True)
        if want[:6] != got[:6] or abs(float(want[6]) - float(got[6])) > .000002
        or want[7:10] != got[7:10] or args.sound and want[10] != got[10]
    ]
    if mismatches:
        for row in mismatches[:15]:
            print(row)
        raise RuntimeError(f"Ground-item Press differs from Java at {len(mismatches)} ticks.")
    print(f"Ground-item Press matched {len(actual)} Java ticks of landing, head travel and sheet output.")
    if args.sound:
        print("All six Java impact cues matched tick, position, volume, and pitch.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for attribute in ("ctl", "client", "resources"):
        parser.add_argument(attribute, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/ground-item-press-java.csv")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--sound", action="store_true")
    run(parser.parse_args())
