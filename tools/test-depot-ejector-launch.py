#!/usr/bin/env python3
"""Replay Java Create's powered Weighted Ejector item launch into an empty Depot."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
EJECTOR = "5 105 -11"
DEPOT = "9 105 -11"
POWER = "4 105 -11"
ITEM = "minecraft:iron_ingot"
SOUND_POSITIONS = {
    "minecraft:block.wooden_trapdoor.close": (5.5, 105.5, -10.5),
    "minecraft:block.chest.open": (5.5, 105.5, -10.5),
    "create:depot_plop": (9.5, 105.5, -10.5),
    "minecraft:block.wooden_button.click_off": (5.5, 105.5, -10.5),
}


def setup(control):
    control.commands((
        "/fill 4 104 -13 10 104 -9 minecraft:smooth_stone",
        "/fill 4 105 -13 10 111 -9 minecraft:air",
        "/gamemode spectator",
        "/tp @s 8.5 106 -10.5",
        f"/setblock {POWER} minecraft:redstone_block",
        f"/setblock {EJECTOR} create:weighted_ejector[facing=east]{{HorizontalDistance:4,VerticalDistance:0}}",
        f"/setblock {DEPOT} create:depot",
        "/setblock 5 105 -12 create:creative_motor[facing=south]{ScrollValue:128}",
    ))


def count(reply, item=ITEM):
    match = re.search(r"\bcount: (\d+)", reply) if item in reply else None
    return int(match[1]) if match else 0


def value(reply):
    match = re.search(r"(-?\d+(?:\.\d+)?)[df]?$", reply)
    return float(match[1]) if match else None


def launch_sounds(control, windup):
    marker = "CREATE_ELEVATOR_PLAYBACK "
    results = []
    for line in (control.socket.parent / "ctl.log").read_text().splitlines():
        if marker not in line:
            continue
        cue, source, x, y, z, volume, pitch = line.split(marker, 1)[1].split(",")
        if cue not in SOUND_POSITIONS or (not windup and cue == "minecraft:block.wooden_button.click_off"):
            continue
        if tuple(map(float, (x, y, z))) != SOUND_POSITIONS[cue]:
            raise RuntimeError(f"Wrong Weighted Ejector sound position {line}")
        category = "block" if source == "4" else source
        results.append(f"{cue}/{category}/{float(volume):.6f}/{float(pitch):.6f}")
    return results


def run(args):
    reference = args.reference
    if reference is None:
        filename = "depot-ejector-launch-java.csv"
        if args.occupied:
            filename = "depot-ejector-blocked-java.csv"
        elif args.windup:
            filename = "depot-ejector-windup-java.csv"
        reference = ROOT / "fixtures" / filename
    with reference.open() as source:
        rows = csv.reader(source)
        header, expected = next(rows), list(rows)
    actual = []
    heard = 0
    if args.windup:
        args.sound = True
    if args.sound:
        os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    world = "WeightedEjectorBlocked" if args.occupied else "WeightedEjectorLaunch"
    if args.windup:
        world += "Windup"
    if args.multiplayer:
        world += "LAN"
    with ExitStack() as stack:
        control = stack.enter_context(fixture_world(args, world, render=args.sound, pack=args.pack))
        if args.windup:
            start = control.clock()
            if (start + int(expected[0][0])) % 2 != int(expected[0][-2]):
                control.step_to(start + 1)
        setup(control)
        guest = None
        if args.multiplayer:
            port = control.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejector-lan-")))
            name = "EjectorGuest"
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario="weighted-ejector",
                render=args.sound, pack=args.pack,
            ))
            multiplayer.until("guest enters the Ejector fixture", lambda: any(
                player["name"] == name and player["placed"]
                for player in control.call("lan", "status")["guests"]
            ))
            control.command(f"/tp {name} 7.5 105 -10.5")
            multiplayer.until("guest sees the receiving Depot",
                              lambda: guest.call("block", 9, 105, -11)["block"] == "create:depot")
        if args.occupied and not guest:
            control.commands(("/gamemode survival", "/tp @s 7.5 105 -10.5"))
        start = control.clock()
        for row in expected:
            tick = int(row[0])
            control.step_to(start + tick)
            if tick == 12:
                if args.occupied:
                    control.command(
                        f'/data merge block {DEPOT} '
                        '{Items:[{Slot:0b,id:"minecraft:diamond",count:1}],BeltPosition:0.5f}'
                    )
                control.commands((
                    f'/data merge block {EJECTOR} {{Items:[{{Slot:0b,id:"{ITEM}",count:3}}],BeltPosition:0.5f}}',
                    f"/setblock {POWER} minecraft:air",
                ))
            elif args.occupied and tick == 20:
                actor = guest or control
                actor.call("interact", 9, 105, -11, "up")
                multiplayer.until("player clears the receiving Depot",
                                  lambda: multiplayer.count(actor, "minecraft:diamond") == 1)
            state, lid, rpm, contents, flying, received, received_at = control.commands((
                f"/data get block {EJECTOR} State", f"/data get block {EJECTOR} Lid.Value",
                f"/data get block {EJECTOR} Speed", f"/data get block {EJECTOR} Items",
                f"/data get block {EJECTOR} LaunchedItems", f"/data get block {DEPOT} Items",
                f"/data get block {DEPOT} BeltPosition",
            ))
            matched = re.search(r"\b(CHARGED|LAUNCHING|RETRACTING)\b", state)
            lid_height = value(lid)
            speed = value(rpm)
            if matched is None or lid_height is None or speed is None:
                raise RuntimeError(f"Missing Weighted Ejector state at tick {tick}: {(state, lid, rpm)}")
            age = re.search(r"\bTime: (\d+)", flying)
            delivered = count(received) or -count(received, "minecraft:diamond")
            events = []
            if args.sound:
                expected_sounds = [] if row[-1] == "-" else row[-1].split(";")
                for observer in (control, guest) if guest else (control,):
                    if expected_sounds:
                        target = heard + len(expected_sounds)
                        multiplayer.until(f"Ejector launch audio at tick {tick}",
                                          lambda: len(launch_sounds(observer, args.windup)) >= target)
                    events = launch_sounds(observer, args.windup)[heard:]
                    if events != expected_sounds:
                        role = "host" if observer is control else "guest"
                        raise RuntimeError(f"Ejector playback at tick {tick} for {role}: {events}")
                heard += len(events)
                if control.clock() != start + tick:
                    raise RuntimeError("Sound capture advanced the world tick.")
            actual.append([
                str(tick), matched[1], f"{lid_height:.6f}", f"{speed:.2f}",
                str(count(contents)), age[1] if age else "-1", str(delivered),
                f"{value(received_at):.6f}" if delivered else "0.000000",
                *([str((start + tick) % 2)] if args.windup else []),
                ";".join(events) or "-",
            ])
        if guest:
            guest.call("interact", 9, 105, -11, "up")
            multiplayer.until("guest retrieves all three ingots", lambda: multiplayer.count(guest, ITEM) == 3)
            if count(control.command(f"/data get block {DEPOT} Items")):
                raise RuntimeError("The receiving Depot still contains ingots after the guest's pickup.")
    if args.trace:
        with args.trace.open("w") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(actual)
    columns = len(header) - int(not args.sound)
    different = [(want, got) for want, got in zip(expected, actual, strict=True)
                 if want[:columns] != got[:columns]]
    if different:
        raise RuntimeError(f"Weighted Ejector launch differs on {len(different)} Java ticks. First {different[:10]}")
    print(f"Weighted Ejector charge, launch, and delivery matched all {len(actual)} original Java ticks.")
    if args.windup:
        print("The original nine wind-up clicks matched their exact phase and pitch.")
    if args.multiplayer:
        print("The LAN guest collected all three ingots from the receiving Depot.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path)
    course = parser.add_mutually_exclusive_group()
    course.add_argument("--occupied", action="store_true")
    course.add_argument("--windup", action="store_true")
    parser.add_argument("--multiplayer", action="store_true")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--sound", action="store_true")
    run(parser.parse_args())
