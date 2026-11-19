#!/usr/bin/env python3
"""Check ordinary and parcel item poses drawn during Weighted Ejector flight."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
import json
from math import cos, radians, sin
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
wrench = import_module("test-ejector-wrench-preview")
lid = import_module("test-depot-ejector-visual")
ITEM = "minecraft:iron_ingot"
PACKAGE = "create:cardboard_package_12x12"
TRACE = "CREATE_EJECTOR_FLIGHT_RENDER "
YAW = {"north": 180, "east": -270, "west": -90, "south": 0}


def expected(name, package, time, motion):
    vx, vy, flight_ticks = motion
    dx, dz = next(signs for signs, facing in lid.DIRECTIONS.items() if facing == name)
    correction = min(time / flight_ticks, 1.0) ** 3
    across = wrench.f32(-10.6033 * vx * (0.91 ** time - 1.0))
    f = 0.98 ** time
    height = wrench.f32(-49.4983 * vy * f + 49.4983 * vy - 194.033 * f - 3.92 * time + 194.033)
    distance = across + (4.0 - across) * correction
    pitch = 0.0 if package else radians(wrench.f32(time * 40.0))
    yaw = radians(wrench.f32(time * 20.0) if package else YAW[name])
    scale = 1.5 if package else .5
    offset = [0.5 + dx * distance, 0.625 + height * (1.0 - correction * 0.5),
              0.4375 + dz * distance]
    if package:
        offset[1] += 0.25
    points = []
    for x, y, z in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)):
        y, z = y - 0.125, z + 0.0625
        y, z = y * cos(pitch) - z * sin(pitch), y * sin(pitch) + z * cos(pitch)
        x, z = x * cos(yaw) + z * sin(yaw), -x * sin(yaw) + z * cos(yaw)
        points.extend(a + scale * b for a, b in zip(offset, (x, y, z), strict=True))
    return points


def verify_java(path, motion):
    seen = set()
    normal = set()
    with path.open() as source:
        for row in csv.reader(source):
            label, *fields = row
            if label != "facing":
                name, package, time, maximum = label, fields[0] == "true", float(fields[1]), float(fields[2])
                if not fields[3:]:
                    assert time > maximum, row
                    seen.add((name, package))
                else:
                    pose = list(map(float, fields[3:]))
                    error = max(abs(a - b) for a, b in zip(pose, expected(name, package, time, motion), strict=True))
                    assert time <= maximum and error < 0.000015, (row, error)
                    normal.add((name, package))
    assert len(normal) == 8 and len(seen) == 8, (normal, seen)


def rendered(log, offset, age, motion):
    frames = {}
    expired = set()
    payload = wrench.read_since(log, offset)
    for line in re.findall(rf"{TRACE}([^\n\r]+)", payload):
        try:
            x, z, item, time, _, vertices, encoded = line.split(",", 6)
            time = float(time)
            heading = lid.DIRECTIONS[int(x), int(z)]
            if time >= 21 and int(vertices) > 0 and item in (ITEM, PACKAGE):
                expired.add((heading, item))
            if age <= time <= age + 1 and int(vertices) > 0 and item in (ITEM, PACKAGE):
                coords = [element for row in json.loads(encoded) for element in row]
                error = max(abs(a - b) for a, b in zip(
                    coords, expected(heading, item == PACKAGE, time, motion), strict=True))
                key = (heading, item)
                frames[key] = max(frames.get(key, 0), error)
        except (ValueError, KeyError, TypeError):
            continue
    return frames, expired


def setup(host):
    commands = (
        "/fill 3 103 -14 14 103 -4 minecraft:smooth_stone",
        "/fill 3 104 -14 14 111 -4 minecraft:air",
        *(f'/setblock {lid.position(name)} create:weighted_ejector[facing={name}]'
          '{HorizontalDistance:4,VerticalDistance:0}' for name in lid.POSITIONS),
        "/gamemode spectator @s",
        "/tp @s 8.5 107.8 -4.5",
    )
    host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in commands))
    host.call("look-at", 8.5, 104.5, -10.5)


def show(host, age):
    stacks = ",".join(
        f'{{Stack:{{id:"{item}",count:1}},Time:{sample}}}'
        for sample in (age, 21) for item in (ITEM, PACKAGE)
    )
    host.commands(f'/data merge block {lid.position(name)} {{LaunchedItems:[{stacks}]}}' for name in lid.POSITIONS)


def main():
    parser = argparse.ArgumentParser()
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/weighted-ejector-flight-pose-java.csv")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/weighted-ejector-wrench-java.csv").open() as source:
        row = next(csv.DictReader(source))
        motion = tuple(float(row[name]) for name in ("x_motion", "y_motion", "flight_ticks"))
    verify_java(args.reference, motion)
    os.environ["CREATE_EJECTOR_FLIGHT_RENDER"] = "1"
    errors = []
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "EjectorFlightVisual", render=True, pack=args.pack))
        setup(host)
        peers = {"host": host}
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-eject-flight-")))
            name = "EjectFlightGuest"
            guest = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, render=True, scenario="ejector-flight", pack=args.pack,
            ))
            mp.until("render guest enters the Ejector flight fixture", lambda: any(
                player["name"] == name and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            for command in (f"/gamemode spectator {name}", f"/tp {name} 8.5 107.8 -4.5"):
                host.call("command", command)
            mp.until("render guest reaches the observation point", lambda:
                     guest.call("state")["player"]["position"] == [8.5, 107.8, -4.5])
            guest.call("look-at", 8.5, 104.5, -10.5)
            peers["guest"] = guest
        for age in (1, 7, 13):
            logs = {role: peer.socket.parent / "ctl.log" for role, peer in peers.items()}
            starts = {role: log.stat().st_size for role, log in logs.items()}
            show(host, age)
            for role, peer in peers.items():
                current, expired = {}, set()

                def read():
                    frames, hidden = rendered(logs[role], starts[role], age, motion)
                    current.update(frames)
                    expired.update(hidden)
                    return len(current) == 8

                mp.until(f"{role} has rendered all eight flying item model poses", read)
                if expired:
                    print(f"{role} incorrectly drew expired items at sample {age}: {sorted(expired)}")
                errors.extend((role, age, heading, item, "expired") for heading, item in sorted(expired))
                for (heading, item), error in current.items():
                    if error >= 0.00002:
                        errors.append((role, age, heading, item, round(error, 6)))
        print(f"Captured {len(peers) * 24} flying item poses and checked the visibility cutoff.")
        if errors:
            raise AssertionError(f"{len(errors)} Horizon flying item poses differ from Java, first cases {errors[:8]}")


if __name__ == "__main__":
    main()
