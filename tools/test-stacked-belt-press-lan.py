#!/usr/bin/env python3
"""Check both clients hear the Java Press cues and the guest collects all three sheets."""
import argparse
import csv
from importlib import import_module
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

press = import_module("test-stacked-belt-press")
multiplayer = import_module("test-multiplayer")
SHEET = "create:iron_sheet"
GUEST = "PressGuest"


def deliver(guest, count):
    guest.call("key", "9", "tap")
    guest.call("interact", *map(int, press.belt.DEPOT.split()), "up")
    multiplayer.until(f"guest received sheet {count}",
                      lambda: multiplayer.count(guest, SHEET) == count)


def depot_slides(control):
    marker = "CREATE_ELEVATOR_PLAYBACK "
    at = tuple(float(value) + .5 for value in press.belt.DEPOT.split())
    slide_events = []
    for line in (control.socket.parent / "ctl.log").read_text().splitlines():
        if marker not in line:
            continue
        cue, source, x, y, z, volume, pitch = line.split(marker, 1)[1].split(",")
        if cue != "create:depot_slide":
            continue
        if tuple(map(float, (x, y, z))) != at:
            raise RuntimeError(f"Wrong Depot slide position: {line}")
        category = "block" if source == "4" else source
        slide_events.append((cue, category, f"{float(volume):.6f}", f"{float(pitch):.6f}"))
    return slide_events


def run(args, scratch):
    with args.reference.open() as file:
        expected = list(csv.DictReader(file))
    slides = {}
    if args.depot_slide:
        with args.slide_reference.open() as file:
            for row in csv.DictReader(file):
                tick = int(row["tick"])
                slides[tick] = [(row["cue"], row["category"], row["volume"], row["pitch"])]
    os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    with fixture_world(args, "StackedBeltPressLAN", press.belt.STRUCTURE, render=True, pack=args.pack) as host:
        press.setup(host)
        network = host.call("lan", "open", "0", "commands", "force")
        with multiplayer.joined_client(
            args, scratch, f"127.0.0.1:{network['port']}", GUEST,
            scenario="stacked-belt-press", render=True, pack=args.pack,
        ) as guest:
            multiplayer.until("guest entered", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} 9.5 104 -8.5"))
            multiplayer.until("guest beside the Depot", lambda: (
                abs(guest.call("state")["player"]["position"][2] + 8.5) < .01
            ))
            start = host.clock()
            heard = 0
            slides_heard = 0
            delivered = 0
            for row in expected:
                tick = int(row["tick"])
                if tick:
                    host.step_to(start + tick)
                cues = [] if row["sounds"] == "-" else row["sounds"].split(";")
                slide = slides.get(tick, [])
                for name, control in (("host", host), ("guest", guest)):
                    if cues:
                        multiplayer.until(f"{name} heard the Press at tick {tick}",
                                          lambda: len(press.playback(control)) >= heard + len(cues))
                    audible = press.playback(control)[heard:]
                    if cues != audible:
                        raise RuntimeError(f"{name} tick {tick} expected {cues}, got {audible}")
                    if args.depot_slide:
                        if slide:
                            multiplayer.until(f"{name} heard the Depot slide at tick {tick}",
                                              lambda: len(depot_slides(control)) >= slides_heard + 1)
                        recent = depot_slides(control)[slides_heard:]
                        if slide != recent:
                            raise RuntimeError(f"{name} at tick {tick} expected {slide}, heard {recent}.")
                heard += len(cues)
                slides_heard += len(slide)
                total = int(row["delivered"])
                depot = host.command(f"/data get block {press.belt.DEPOT} Items")
                if (SHEET in depot) != (total > delivered):
                    raise RuntimeError(f"Tick {tick} has unexpected depot contents: {depot}")
                if total > delivered:
                    deliver(guest, total)
                    delivered = total
                    depot = host.command(f"/data get block {press.belt.DEPOT} Items")
                    if SHEET in depot:
                        raise RuntimeError(f"Guest's sheet remained on the host Depot at tick {tick}")
                if host.clock() != start + tick:
                    raise RuntimeError(f"The host tick advanced during measurement at {tick}")
            if multiplayer.count(guest, SHEET) != 3 or heard != 6:
                raise RuntimeError("The guest must collect all three sheets and hear all six cues.")
    print("Host and guest heard all six original Press cues on the Java ticks.")
    print("The guest took the three sheets off the Depot at Java ticks 51, 78, and 105.")
    if args.depot_slide:
        print(f"Both clients heard all {slides_heard} original Belt-to-Depot slide cues.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/stacked-belt-press-java.csv")
    parser.add_argument("--depot-slide", action="store_true")
    parser.add_argument("--slide-reference", type=Path, default=ROOT / "fixtures/belt-depot-slide-java.csv")
    with TemporaryDirectory(prefix="hc-press-lan-") as directory:
        run(parser.parse_args(), Path(directory))
