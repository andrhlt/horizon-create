#!/usr/bin/env python3
"""Catch and deposit packages with a muted client near or far from the Frogport."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from math import cos, radians, sin
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

outbound = import_module("test-chain-conveyor-outbound")
multiplayer = import_module("test-multiplayer")
chain, player = outbound.chain, outbound.player
A, B, PORT = outbound.A, outbound.B, outbound.PORT
POS = r"\[17, 100, -10\]"
START = re.compile(rf"CREATE_FROGPORT_PACKAGE_START {POS},(\d+),(\d+),(true|false)")
SOUND = re.compile(rf"CREATE_FROGPORT_SOUND {POS},(\d+),(create:frogport_\w+),([\d.]+),([\d.]+),(\d+)")
ROPE = re.compile(rf"CREATE_FROGPORT_ROPE {POS},(\d+),([^\r\n]+)")
ENV = {"CREATE_FROGPORT_PACKAGE_EFFECTS": "1", "HORIZON_NO_AUDIO": "1"}


def read_fixture(name):
    with (ROOT / "fixtures" / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def check_effects(log, start, near):
    world = read_fixture("chain-conveyor-world-java.csv")
    outbound = read_fixture("chain-conveyor-outbound-java.csv")
    cases = (
        ("catch", next(int(row["tick"]) for row in world if row["scenario"] == "straight"
                       and row["frogport_custody"].startswith("animation:"))),
        ("deposit", next(int(row["tick"]) for row in outbound if row["animated"] == "true")),
    )
    starts = [(int(local), int(server) - start, deposit == "true")
              for local, server, deposit in START.findall(log)]
    assert [(tick, deposit) for _, tick, deposit in starts] == [
        (cases[0][1], False), (cases[1][1], True),
    ], starts
    all_sounds = SOUND.findall(log)
    all_particles = ROPE.findall(log)
    effects = read_fixture("frogport-package-effects-java.csv")
    expected_anchor = (B[0] + 0.5 + sin(radians(150)) * 0.875,
                       B[1] + 0.375, B[2] + 0.5 + cos(radians(150)) * 0.875)
    for (local, _, _), (action, tick) in zip(starts, cases, strict=True):
        scenario = f"{action}_{'near' if near else 'remote'}"
        rows = [row for row in effects if row["scenario"] == scenario]
        sounds = [(name, float(volume), float(pitch), int(delay))
                  for frame, name, volume, pitch, delay in all_sounds if int(frame) == local]
        reference = [
            (row["id"], float(row["volume_or_dx"]),
             float(row["pitch_or_dy"]) * (2 if row["id"] == "create:frogport_open" else 1),
             0)
            for row in rows if row["kind"] == "sound"
        ]
        assert sounds == reference, (scenario, sounds, reference)
        particles = [tuple(map(float, fields.split(","))) for frame, fields in all_particles
                     if int(frame) == local]
        assert len(particles) == sum(row["kind"] == "particle" for row in rows), (scenario, particles)
        for x, y, z, ax, ay, az in particles:
            assert (x, z) == (ax, az) and ay - 0.25 <= y <= ay, (x, y, z, ax, ay, az)
            assert all(abs(observed - expected) < 0.0001
                       for observed, expected in zip((ax, ay, az), expected_anchor, strict=True))
        print(f"{scenario} at Java tick {tick}: {len(sounds)} cues and {len(particles)} rope particles")
    assert all(int(row[0]) in {event[0] for event in starts} for row in all_sounds + all_particles)


def run(args):
    role = "Lan" if args.lan else "Solo"
    proximity = "Remote" if args.remote else "Near"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(
            args, f"FrogportEffects{role}{proximity}", pack=args.pack,
            render=not args.lan, env=ENV,
        ))
        chain.setup(host, A, B, (8, 101, -10), PORT, (7, 0, 0), False, warm=7)
        chain.merge(host, PORT, '{AddressFilter:"Lab-In",Target:{RelativePos:[I;-2,2,0],ChainPosition:150f}}')
        chain.merge(host, B, "{PackagePorts:[{Port:[I;2,-2,0],ChainPosition:150f}]}")
        host.command("/fill 14 99 -10 39 99 -3 minecraft:stone")
        observer, name = host, "@s"
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            name = "ParcelObserver"
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-frogport-effects-")))
            observer = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, pack=args.pack, render=True,
                scenario=f"frogport-effects-{proximity}", env=ENV,
            ))
            multiplayer.until("the parcel observer to join", lambda:
                              any(g["name"] == name and g["placed"] for g in host.call("lan", "status")["guests"]))
        position = (37.5, 100.0, -9.5) if args.remote else (17.5, 100.0, -5.5)
        host.command(f"/tp {name} {chain.coords(position)}")
        multiplayer.until("the observer to reach the testing location", lambda:
                          observer.call("state")["player"]["position"] == list(position))
        observer.call("look-at", 16.0, 101.5, -9.5)
        observer.call("wait", 4)
        log = observer.socket.parent / "ctl.log"
        offset = len(log.read_text())
        start = host.clock()
        for tick in range(1, 48):
            host.step_to(start + tick)
            if tick == 2:
                cargo = chain.stack("Lab-In", "paper", 3)
                chain.merge(host, A, f"{{Packages:[{{Item:{cargo},Position:40f}}]}}")
            if tick == 35:
                cargo = chain.stack("Away", "paper", 4)
                existing = player.get(host, PORT, "Items")
                assert chain.payload(existing) == "Lab-In:paper:3", existing
                chain.merge(host, PORT, "{Items:" + existing.rstrip("]") + ",{Slot:1b," + cargo[1:] + "]}")
            if tick in (24, 37, 47):
                observer.call("wait", 4)
        check_effects(log.read_text()[offset:], start, not args.remote)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--remote", action="store_true")
    run(parser.parse_args())
