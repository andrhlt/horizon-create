#!/usr/bin/env python3
"""Replay the original inward Belt Funnel flap driven by Ejector export."""
from argparse import ArgumentParser
from contextlib import ExitStack
import csv
from importlib import import_module
import json
from math import isclose, pi, sin, tau
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
wrench = import_module("test-ejector-wrench-preview")
AGE_ROWS = "CREATE_FUNNEL_FLAP_RENDER "
PLAYBACK = "CREATE_ELEVATOR_PLAYBACK "
SOUNDS = [
    ("create:funnel_flap", 0.125, 1.5),
    ("create:funnel_flap_compounded_1", 0.0425, 0.75),
]
POSITION = (5.5, 105.5, -10.5)
GUEST = "FlapGuest"
VIEW = [6.5, 106, -7.5]


def cue_logs(path, offset):
    sound_events = []
    for line in re.findall(rf"{PLAYBACK}([^\r\n]+)", wrench.read_since(path, offset)):
        try:
            cue, source, x, y, z, volume, pitch = line.split(",")
            if (cue, float(volume), float(pitch)) in SOUNDS:
                assert (float(x), float(y), float(z)) == POSITION, line
                assert source == "4", line
                sound_events.append((cue, float(volume), float(pitch)))
        except ValueError:
            continue
    return sound_events


def poses(path, offset):
    rows = {}
    text = wrench.read_since(path, offset)
    for line in re.findall(rf"{AGE_ROWS}([^\r\n]+)", text):
        try:
            x, y, z, tick, age, partial, previous, current, flap, vertices, encoded = line.split(",", 10)
            if (int(x), int(y), int(z)) != (5, 105, -11):
                continue
            points = json.loads(encoded)
            if int(vertices) > 0 and len(points) == 4:
                rows[int(age)] = (int(tick), float(partial), float(previous), float(current), float(flap), points)
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
    return rows


def angle(flap, segment):
    intensity = (1., 2., 3., 1.5)[segment]
    radians = wrench.f32(wrench.f32(1 - abs(flap)) * pi * intensity)
    index = int(wrench.f32(radians * wrench.f32(10430.378))) & 65535
    sine = wrench.f32(sin(index * tau / 65536.))
    normal = wrench.f32(wrench.f32(sine * 30) * flap)
    return normal * (0.5 if flap < 0 else 1.0)


def verify(rows, original, role):
    observed = 0
    for age, (_, partial, prev, curr, flap, angles) in rows.items():
        if age not in original:
            continue
        expected = original[age]
        for a, b in ((prev, expected[0]), (curr, expected[2]), (flap, prev + (curr - prev) * partial)):
            assert isclose(a, b, abs_tol=1e-6), (role, age, a, b)
        for segment, actual in enumerate(angles):
            assert isclose(actual, angle(flap, segment), abs_tol=1e-5), (role, age, segment, actual, flap)
        observed += 1
    assert observed == len(original), (role, observed, sorted(rows))
    return observed


def setup(host, pushing):
    inputs = (
        "/fill 2 103 -15 12 103 -8 minecraft:smooth_stone",
        "/fill 2 104 -15 12 110 -8 minecraft:air",
        "/setblock 5 106 -11 minecraft:redstone_block" if pushing else "/setblock 4 104 -11 minecraft:redstone_block",
        "/setblock 5 104 -11 create:depot" if pushing else
        "/setblock 5 104 -11 create:weighted_ejector[facing=east]{HorizontalDistance:4,VerticalDistance:0}",
        "/setblock 5 104 -12 create:creative_motor[facing=south]{ScrollValue:128}",
        "/setblock 6 105 -11 minecraft:barrel",
        f"/setblock 5 105 -11 create:brass_belt_funnel[facing=west,shape={'pushing' if pushing else 'pulling'}]",
        "/gamemode spectator @s",
        "/tp @s 6.5 106 -7.5",
    )
    host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in inputs))
    host.call("look-at", *POSITION)


def main():
    parser = ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--pushing", action="store_true")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    os.environ["CREATE_FUNNEL_FLAP_RENDER"] = "1"
    os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    java_fixture = "belt-funnel-pushing-flap-java.csv" if args.pushing else "weighted-ejector-funnel-flap-java.csv"
    reference = args.reference or ROOT / "fixtures" / java_fixture
    with reference.open() as file:
        source = csv.reader(file)
        next(source)
        original = {int(age): list(map(float, values)) for age, *values in source}
    for values in original.values():
        for segment, observed in enumerate(values[3:]):
            assert isclose(observed, angle(values[1], segment), abs_tol=1e-5)
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "EjectorFunnelFlap", render=True, pack=args.pack))
        setup(host, args.pushing)
        clients = {"host": host}
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejfl-")))
            guest = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST, render=True,
                scenario="ejector-funnel-flap", pack=args.pack,
            ))
            mp.until("the viewing guest joins", lambda: any(
                player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            host.call("command", f"/gamemode spectator {GUEST}")
            host.call("command", f"/tp {GUEST} 6.5 106 -7.5")
            mp.until("the guest reaches the Funnel", lambda: guest.call("state")["player"]["position"] == VIEW)
            guest.call("look-at", *POSITION)
            clients["guest"] = guest
        start = host.clock()
        for tick in range(1, 13):
            host.step_to(start + tick)
        logs = {role: game.socket.parent / "ctl.log" for role, game in clients.items()}
        offsets = {role: log.stat().st_size for role, log in logs.items()}
        if args.pushing:
            host.commands((
                '/data merge block 6 105 -11 {Items:[{Slot:0b,id:"minecraft:iron_ingot",count:1}]}',
                "/setblock 5 106 -11 minecraft:air",
            ))
        else:
            host.commands((
                '/data merge block 5 104 -11 {Items:[{Slot:0b,id:"minecraft:iron_ingot",count:3}],BeltPosition:0.5f}',
                "/setblock 4 104 -11 minecraft:air",
            ))
        first_frame = 14 if args.pushing else 15
        for tick in range(13, first_frame + len(original)):
            host.step_to(start + tick)
            age = tick - first_frame
            if age in original:
                for role, log in logs.items():
                    def rendered():
                        row = poses(log, offsets[role]).get(age)
                        return row is not None and row[0] == start + tick

                    mp.until(f"{role} renders Funnel flap age {age} at game tick {start + tick}", rendered)
        if args.pushing:
            assert "minecraft:iron_ingot" in host.command("/data get block 5 104 -11 Items")
        for role, log in logs.items():
            rows = poses(log, offsets[role])
            if args.trace:
                args.trace.with_suffix(f".{role}.log").write_text(wrench.read_since(log, offsets[role]))
            actual = cue_logs(log, offsets[role])
            assert actual == SOUNDS * (1 if args.pushing else 2), (role, actual, sorted(rows))
            observed = verify(rows, original, role)
            print(f"{role} matched {observed} original four-segment flap samples and {len(actual)} layered playbacks.")


if __name__ == "__main__":
    main()
