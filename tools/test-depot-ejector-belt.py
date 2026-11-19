#!/usr/bin/env python3
"""Compare Java moving Belt insertion and the Weighted Ejector's combined output."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

belt = import_module("test-horizontal-belt")
launch = import_module("test-depot-ejector-launch")
multiplayer = import_module("test-multiplayer")
track = import_module("test-track-crafting")
EJECTOR = "9 104 -11"
DEPOT = "13 104 -11"


def setup(control):
    belt.connect(control)
    control.commands((
        "/fill 10 103 -14 14 103 -9 minecraft:smooth_stone",
        f"/setblock {belt.MOTOR} create:creative_motor[facing=south]{{ScrollValue:-48}}",
        f"/setblock {EJECTOR} create:weighted_ejector[facing=east]"
        "{HorizontalDistance:4,VerticalDistance:0,ScrollValue:3}",
        "/setblock 9 104 -12 create:creative_motor[facing=south]{ScrollValue:128}",
        f"/setblock {DEPOT} create:depot",
        "/gamemode spectator @s",
        "/tp @s 11.5 105 -9.5",
    ))


def inject(control, count):
    control.command(
        f'/data merge block {belt.START} {{Inventory:{{PositiveOrder:1b,Items:['
        f'{{Item:{{id:"{launch.ITEM}",count:{count}}},PrevPos:0.4375f,Pos:0.4375f,Angle:180}}]}}}}'
    )


def run(args):
    with args.reference.open() as source:
        data = csv.reader(source)
        header, expected = next(data), list(data)
    world = "EjectorBeltLAN" if args.multiplayer else "EjectorBelt"
    actual = []
    with ExitStack() as stack:
        control = stack.enter_context(fixture_world(args, world, belt.STRUCTURE, render=True, pack=args.pack))
        setup(control)
        guest = None
        if args.multiplayer:
            port = control.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejector-belt-")))
            name = "EjectBeltGuest"
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario="ejector-belt", pack=args.pack,
            ))
            multiplayer.until("the guest enters the fixture", lambda: any(
                player["name"] == name and player["placed"]
                for player in control.call("lan", "status")["guests"]
            ))
            control.command(f"/tp {name} 11.5 104 -10.5")
            multiplayer.until("guest sees the receiving Depot",
                              lambda: guest.call("block", 13, 104, -11)["block"] == "create:depot")
        start = control.clock()
        for row in expected:
            tick = int(row[0])
            control.step_to(start + tick)
            if tick == 12:
                inject(control, 3)
            state, held, flying, received, incoming, speed, belt_items = control.commands((
                f"/data get block {EJECTOR} State", f"/data get block {EJECTOR} Items",
                f"/data get block {EJECTOR} LaunchedItems", f"/data get block {DEPOT} Items",
                f"/data get block {EJECTOR} Incoming", f"/data get block {belt.START} Speed",
                f"/data get block {belt.START} Inventory.Items",
            ))
            matched = re.search(r"\b(CHARGED|LAUNCHING|RETRACTING)\b", state)
            age = re.search(r"\bTime: (\d+)", flying)
            pending = re.findall(r"\bPos: (-?\d+(?:\.\d+)?)(?:f)?", incoming)
            cargo = [stack for stack in track.compounds(belt_items) if launch.ITEM in stack]
            first_count = track.stack_count(cargo[0]) if cargo else 0
            position = track.field(cargo[0], "Pos") if cargo else 0
            drive = launch.value(speed)
            if matched is None or drive is None:
                raise RuntimeError(f"Missing Ejector or Belt state at tick {tick}: {(state, speed)}")
            actual.append([
                str(tick), matched[1], str(launch.count(held)), age[1] if age else "-1",
                str(launch.count(received)), str(len(pending)), f"{float(pending[0]) if pending else 0:.6f}",
                str(int(drive)), str(first_count), f"{position:.7f}",
            ])
        if guest:
            guest.call("interact", 13, 104, -11, "up")
            multiplayer.until("guest collects the output", lambda: multiplayer.count(guest, launch.ITEM) == 3)
    if args.trace:
        with args.trace.open("w") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(actual)
    differences = [(want, got) for want, got in zip(expected, actual, strict=True)
                   if want[:6] != got[:6] or want[7:9] != got[7:9]
                   or abs(float(want[6]) - float(got[6])) > .000002
                   or abs(float(want[9]) - float(got[9])) > .000001]
    if differences:
        raise RuntimeError(f"Belt-fed Ejector differed on {len(differences)} Java ticks: {differences[:8]}")
    print(f"Moving Belt, Ejector merging, and Depot delivery matched all {len(actual)} original Java ticks.")
    if args.multiplayer:
        print("The guest collected all three merged ingots from the Depot.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/depot-ejector-belt-java.csv")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    run(parser.parse_args())
