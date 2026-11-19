#!/usr/bin/env python3
"""Immediately deposit and retrieve an item from a newly placed Depot."""
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
ITEM = "minecraft:iron_ingot"
DEPOT = (5, 105, -11)
POSITION = " ".join(map(str, DEPOT))


def sample(control, actor, action, start):
    storage = control.command(f"/data get block {POSITION} Items")
    match = re.search(r"\bcount: (\d+)", storage) if ITEM in storage else None
    return (
        action, str(control.clock() - start), str(multiplayer.count(actor, ITEM)),
        match[1] if match else "0",
    )


def cues(control):
    marker = "CREATE_ELEVATOR_PLAYBACK "
    output = (control.socket.parent / "ctl.log").read_text()
    rows = []
    for line in output.splitlines():
        if marker not in line:
            continue
        sound, source, x, y, z, volume, pitch = line.split(marker, 1)[1].split(",")
        if sound != "create:depot_slide":
            continue
        if tuple(map(float, (x, y, z))) != tuple(value + .5 for value in DEPOT):
            raise RuntimeError(f"Depot sound came from the wrong position: {line}")
        category = "block" if source == "4" else source
        rows.append((sound, category, f"{float(volume):.6f}", f"{float(pitch):.6f}"))
    return rows


def run(args):
    with args.reference.open() as source:
        expected = list(csv.reader(source))[1:]
    if args.slide:
        os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
        with args.slide_reference.open() as source:
            rows = list(csv.reader(source))[1:]
        (cue_tick, *expected_cue), = rows
    scenario = "DepotFirstClickLAN" if args.multiplayer else "DepotFirstClick"
    with ExitStack() as stack:
        control = stack.enter_context(fixture_world(args, scenario, render=True, pack=args.pack))
        actor, target = control, "@s"
        if args.multiplayer:
            port = control.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-depot-slide-")))
            target = "DepotGuest"
            actor = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", target,
                scenario="depot-slide", render=True, pack=args.pack,
            ))
            multiplayer.until("guest entered", lambda: any(
                player["name"] == target and player["placed"]
                for player in control.call("lan", "status")["guests"]
            ))
            control.commands(("/gamemode spectator @s", "/tp @s 8.5 106 -10.5"))
        observers = (control, actor) if args.multiplayer else (control,)
        control.commands((
            "/setblock 7 105 -11 minecraft:smooth_stone",
            f"/tp {target} 7.5 106 -10.5",
            f"/gamemode survival {target}",
            f"/give {target} {ITEM} 3",
        ))
        multiplayer.until("player has the three ingots",
                          lambda: multiplayer.count(actor, ITEM) == 3)
        actor.call("select", ITEM)
        tick = control.clock()
        control.command(f"/setblock {POSITION} create:depot")
        multiplayer.until("player sees the new Depot", lambda: (
            actor.call("block", *DEPOT)["state"].startswith("create:depot")
        ))
        actual = [sample(control, actor, "placed", tick)]
        if args.slide and any(cues(observer) for observer in observers):
            raise RuntimeError("Depot slide played before the item was deposited.")
        actor.call("interact", *DEPOT, "up")
        multiplayer.until("new Depot holds all three ingots",
                          lambda: ITEM in control.command(f"/data get block {POSITION} Items"))
        actual.append(sample(control, actor, "deposited", tick))
        if args.slide:
            for observer in observers:
                multiplayer.until("the first Depot slide cue", lambda: cues(observer))
                if cues(observer) != [tuple(expected_cue)] or control.clock() - tick != int(cue_tick):
                    raise RuntimeError("Depot slide playback differs from the original Java cue.")
        actor.call("interact", *DEPOT, "up")
        multiplayer.until("player retrieves all three ingots",
                          lambda: multiplayer.count(actor, ITEM) == 3)
        actual.append(sample(control, actor, "retrieved", tick))
        if args.slide and any(cues(observer) != [tuple(expected_cue)] for observer in observers):
            raise RuntimeError("Retrieval repeated the Depot slide cue.")
    if list(map(list, actual)) != expected:
        raise RuntimeError(f"Immediate Depot use differs from Java: {actual}, expected {expected}")
    print("Placed the Depot, deposited and retrieved three ingots, all on one frozen game tick.")
    if args.slide:
        nearby = " on both LAN clients" if args.multiplayer else ""
        print(f"The original slide cue matched{nearby} on the Java deposition tick.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/depot-first-click-java.csv")
    parser.add_argument("--slide", action="store_true")
    parser.add_argument("--multiplayer", action="store_true")
    parser.add_argument("--slide-reference", type=Path, default=ROOT / "fixtures/depot-slide-java.csv")
    run(parser.parse_args())
