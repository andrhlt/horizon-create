#!/usr/bin/env python3
"""Replay Java Weighted Ejector output to a Belt that starts while waiting."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

belt = import_module("test-horizontal-belt")
launch = import_module("test-depot-ejector-launch")
obstacle = import_module("test-depot-ejector-obstacle")
track = import_module("test-track-crafting")
EJECTOR = "5 104 -11"
BELT = "9 104 -11"


def setup(control):
    control.commands((
        "/fill 4 103 -14 14 103 -9 minecraft:smooth_stone",
        "/fill 4 104 -14 14 110 -9 minecraft:air",
        f"/setblock {BELT} create:shaft[axis=z]",
        "/setblock 12 104 -11 create:shaft[axis=z]",
        "/give @s create:belt_connector",
    ))
    control.call("tp", 10.5, 104, -8.5)
    control.call("select", "create:belt_connector")
    for _ in range(3):
        if "create:belt_connector" in control.command("/data get entity @s SelectedItem"):
            break
        control.call("wait", 1)
    else:
        raise RuntimeError("The server did not equip the connector")
    for _ in range(2):
        control.call("interact", 9, 104, -11)
        if "CreateBeltFirstShaft" in control.command("/data get entity @s SelectedItem"):
            break
    else:
        raise RuntimeError("The first shaft was never selected")
    for _ in range(5):
        control.step_to(control.clock() + 1)
    control.call("interact", 12, 104, -11)
    for x, part in ((9, "start"), (10, "middle"), (11, "middle"), (12, "end")):
        block = control.call("block", x, 104, -11)["state"]
        if not block.startswith("create:belt[") or f"part={part}" not in block:
            raise RuntimeError(f"Connector did not place the {part} at x={x}: {block}")
    control.commands((
        f"/setblock {EJECTOR} create:weighted_ejector[facing=east]"
        "{HorizontalDistance:4,VerticalDistance:0}",
        "/setblock 5 104 -12 create:creative_motor[facing=south]{ScrollValue:128}",
        "/gamemode spectator @s",
        "/tp @s 8.5 105 -9.5",
    ))


def run(args):
    with args.reference.open() as source:
        data = csv.reader(source)
        header, expected = next(data), list(data)
    actual = []
    with fixture_world(args, "EjectorStoppedBelt", belt.STRUCTURE, render=True, pack=args.pack) as control:
        setup(control)
        start = control.clock()
        for row in expected:
            tick = int(row[0])
            control.step_to(start + tick)
            if tick == 12:
                control.command(
                    f'/data merge block {EJECTOR} '
                    f'{{Items:[{{Slot:0b,id:"{launch.ITEM}",count:3}}],BeltPosition:0.5f}}'
                )
            state, held, flying, belt_data, belt_items = control.commands((
                f"/data get block {EJECTOR} State", f"/data get block {EJECTOR} Items",
                f"/data get block {EJECTOR} LaunchedItems", f"/data get block {BELT}",
                f"/data get block {BELT} Inventory.Items",
            ))
            matched = re.search(r"\b(CHARGED|LAUNCHING|RETRACTING)\b", state)
            age = re.search(r"\bTime: (\d+)", flying)
            cargo = [entry for entry in track.compounds(belt_items) if launch.ITEM in entry]
            first_count = track.stack_count(cargo[0]) if cargo else 0
            position = track.field(cargo[0], "Pos") if cargo else 0
            drive = track.field(belt_data, "Speed")
            if matched is None:
                raise RuntimeError(f"Missing Ejector state at tick {tick}: {state}")
            loose = sum(entry["item"]["count"] for entry in obstacle.items_near(control, launch.ITEM))
            actual.append([
                str(tick), matched[1], str(launch.count(held)), age[1] if age else "-1",
                str(int(drive)), str(first_count), f"{position:.7f}", str(loose),
            ])
            if tick == 24:
                control.command("/setblock 9 104 -12 create:creative_motor[facing=south]{ScrollValue:-48}")
    if args.trace:
        with args.trace.open("w") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(actual)
    differences = [(want, got) for want, got in zip(expected, actual, strict=True)
                   if want[:6] != got[:6] or want[7] != got[7]
                   or abs(float(want[6]) - float(got[6])) > .000001]
    if differences:
        raise RuntimeError(f"Ejector aimed at stopped Belt differed on {len(differences)} Java ticks: {differences[:8]}")
    print(f"Waiting for the Belt, the Ejector’s flight and three-ingot delivery matched all {len(actual)} Java ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/depot-ejector-belt-target-java.csv")
    parser.add_argument("--trace", type=Path)
    run(parser.parse_args())
