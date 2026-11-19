#!/usr/bin/env python3
"""Replay three Java press cycles on a moving stacked belt."""
import argparse
import csv
from importlib import import_module
import os
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

belt = import_module("test-horizontal-belt")
depot = import_module("test-depot-pressing")
track = import_module("test-track-crafting")
multiplayer = import_module("test-multiplayer")
PRESS = "6 106 -11"
PRESS_MOTOR = "6 106 -12"
TICK_SOUND = "CREATE_ELEVATOR_PLAYBACK "


def setup(control):
    belt.connect(control)
    control.commands((
        f"/setblock {belt.MOTOR} create:creative_motor[facing=south]",
        f"/data merge block {belt.MOTOR} {{ScrollValue:-48}}",
        f"/setblock {PRESS_MOTOR} create:creative_motor[facing=south]",
        f"/data merge block {PRESS_MOTOR} {{ScrollValue:128}}",
        f"/setblock {PRESS} create:mechanical_press[facing=south]",
        f"/setblock {belt.DEPOT} create:depot",
    ))
    control.step_to(control.clock() + 1)
    control.command(
        f'/data merge block {belt.START} {{Inventory:{{PositiveOrder:1b,Items:['
        '{Item:{id:"minecraft:iron_ingot",count:3},PrevPos:0.4375f,Pos:0.4375f,Angle:180}]}}'
    )


def cargo(message):
    items = []
    for stack in track.compounds(message):
        count = track.stack_count(stack)
        if count == 0:
            continue
        ident = re.search(r'\bid: "([^"]+)"', stack)
        if ident is None:
            raise RuntimeError(f"Cannot read the transported item: {stack}")
        items.append(
            f'{ident[1]}/{count}/{track.field(stack, "Pos"):.7f}/{int(track.field(stack, "Locked"))}'
        )
    return ";".join(items) or "-"


def playback(control):
    log = control.socket.parent / "ctl.log"
    events = []
    for line in log.read_text().splitlines():
        if TICK_SOUND not in line:
            continue
        identifier, source, x, y, z, volume, pitch = line.split(TICK_SOUND, 1)[1].split(",")
        if not identifier.startswith("create:mechanical_press_activation_belt"):
            continue
        if source not in ("4", "block") or tuple(map(float, (x, y, z))) != (6.5, 106.5, -10.5):
            raise RuntimeError(f"Unexpected press sound position or category: {line}")
        events.append(f"{identifier}/{float(volume):.6f}/{float(pitch):.6f}")
    return events


def sample(control, tick, delivered):
    press, drive, items, output = control.commands((
        f"/data get block {PRESS}", f"/data get block {belt.START} Speed",
        f"/data get block {belt.START} Inventory.Items", f"/data get block {belt.DEPOT} Items",
    ))
    if "create:mechanical_press" not in press:
        raise RuntimeError("The press is missing from the belt rig")
    delivered += sum(track.stack_count(stack) for stack in track.compounds(output)
                     if 'id: "create:iron_sheet"' in stack and depot.scalar(stack, "Slot", -1) == 0)
    speed = re.search(r"(-?\d+(?:\.\d+)?)f?$", drive)
    if not speed:
        raise RuntimeError(f"Could not read belt speed: {drive}")
    mode = depot.scalar(press, "Mode")
    offset = depot.head_offset(press) * (16 / 19 if mode == 0 else 1)
    return [
        str(tick), str(int(float(speed[1]))),
        *(str(depot.scalar(press, key)) for key in ("Speed", "Running", "Finished", "Mode", "Ticks")),
        f"{offset:.6f}", str(delivered), cargo(items),
    ], delivered


def expected_cargo(left, right):
    if left == right:
        return True
    a, b = left.split(";"), right.split(";")
    if len(a) != len(b):
        return False
    for first, second in zip(a, b, strict=True):
        one, two = first.split("/"), second.split("/")
        if len(one) != 4 or len(two) != 4 or one[:2] != two[:2] or one[3] != two[3]:
            return False
        if abs(float(one[2]) - float(two[2])) > .000001:
            return False
    return True


def run(args):
    with args.reference.open() as text:
        rows = csv.reader(text)
        header, expected = next(rows), list(rows)
    actual = []
    if args.sound:
        os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    with fixture_world(args, "StackedBeltPress", belt.STRUCTURE, render=True, pack=args.pack) as control:
        setup(control)
        start = control.clock()
        delivered = 0
        heard = 0
        for tick, expected_row in enumerate(expected):
            if tick:
                control.step_to(start + tick)
            old = delivered
            fields, delivered = sample(control, tick, delivered)
            if delivered != old:
                control.command(f"/item replace block {belt.DEPOT} container.0 with minecraft:air")
            if args.sound:
                if expected_row[-1] != "-":
                    count = len(expected_row[-1].split(";"))
                    multiplayer.until(f"press impact sounds at tick {tick}",
                                      lambda: len(playback(control)) >= heard + count)
                events = playback(control)
                fields.append(";".join(events[heard:]) or "-")
                heard = len(events)
                if control.clock() != start + tick:
                    raise RuntimeError("Sound measurement advanced the simulation tick.")
            else:
                fields.append("-")
            actual.append(fields)
    if args.trace:
        with args.trace.open("w") as text:
            writer = csv.writer(text, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(actual)
    mismatches = []
    for want, got in zip(expected, actual, strict=True):
        if (want[:7] != got[:7] or abs(float(want[7]) - float(got[7])) > .000002
                or want[8] != got[8] or not expected_cargo(want[9], got[9])
                or args.sound and want[10] != got[10]):
            mismatches.append((want, got))
    if mismatches:
        for row in mismatches[:12]:
            print(row)
        raise RuntimeError(f"Stacked Belt Press differs from Java at {len(mismatches)} ticks.")
    print(f"Stacked Belt Press matched {len(actual)} Java ticks of head travel, held cargo and delivery.")
    if args.sound:
        print("All six Java impact cues matched their tick, position, volume, and pitch.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for attribute in ("ctl", "client", "resources"):
        parser.add_argument(attribute, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/stacked-belt-press-java.csv")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--sound", action="store_true")
    run(parser.parse_args())
