#!/usr/bin/env python3
"""Place Create curves as a survival player and compare their live endpoints with Java."""

import argparse
import csv
import json
from math import atan2, dist, pi, tan
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/track_crafting.nbt")
START = (5, 112, -8)


def add(a, b):
    return tuple(x + y for x, y in zip(a, b, strict=True))


def coordinates(pos):
    return " ".join(str(part) for part in pos)


def vector(reply):
    content = reply.partition("[")[2].rpartition("]")[0]
    return tuple(float(word) for word in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", content))


def geometry(starts, axes):
    start, end = starts
    a, b = axes
    angle = abs((atan2(-b[2], -b[0]) - atan2(a[2], a[0]) + pi) % (2 * pi) - pi)
    if angle < 1e-5:
        delta = tuple(y - x for x, y in zip(start, end, strict=True))
        run = abs(delta[0] * a[0] + delta[2] * a[2])
        shift = abs(delta[0] * a[2] - delta[2] * a[0])
        low, high = sorted((run, shift))
        handle = high - low if low > 1.2 and 1 < high / low < 3 else dist(start, end) / 3
    else:
        cross1, cross2 = (-a[2], a[0]), (-b[2], b[0])
        determinant = cross1[0] * cross2[1] - cross1[1] * cross2[0]
        delta = (end[0] - start[0], end[2] - start[2])
        radius = abs((delta[0] * cross1[1] - delta[1] * cross1[0]) / determinant)
        handle = radius * (4.0 / 3.0) * tan(angle / 4)

    def point(t):
        inv = 1.0 - t
        return tuple(inv**3 * p + 3 * inv**2 * t * (p + handle * u)
                     + 3 * inv * t**2 * (q + handle * v) + t**3 * q
                     for p, q, u, v in zip(start, end, a, b, strict=True))

    length = sum(dist(point(i / 16), point((i + 1) / 16)) for i in range(16))
    return handle, length, point


def test_case(control, row, offset=(0, 0, 0), reset=True, validate=True, actor="@s", command_fn=None):
    dedicated_commands = command_fn is not None
    command_fn = command_fn or (lambda text: control.command("/" + text))
    dx, dy, dz, supplied, remaining = (
        int(row[key]) for key in ("dx", "dy", "dz", "supplied", "remaining")
    )
    start = add(START, offset)
    end = add(start, (dx, dy, dz))
    x, y, z = start
    setup = (
        *(("/fill -11 112 -24 25 117 7 minecraft:air",) if reset else ()),
        f"/setblock {coordinates(add(end, (0, -1, 0)))} minecraft:smooth_stone",
        f"/setblock {coordinates(start)} create:track[shape=xo]",
        f"/tp {actor} {x + 0.5 + (2 if dx < 0 else -2)} {y} {z + 0.5}",
        f"/item replace entity {actor} hotbar.0 with create:track {supplied}",
    )
    if not dedicated_commands:
        control.call("script", script="".join(f"command {json.dumps(cmd)}\n" for cmd in setup))
    else:
        for cmd in setup:
            command_fn(cmd.lstrip("/"))
    control.call("wait", 2)
    control.call("select", "create:track")
    control.call("look-at", x + 0.5, y + 0.06, z + 0.5)
    control.call("mouse", "right", "click")
    control.call("wait", 3)
    if not validate:
        start_inventory = ""
    else:
        start_inventory = control.command("/data get entity @s Inventory")
    if validate and "create:track_connecting_from" not in start_inventory:
        raise RuntimeError(f"Case {row['case']} did not select the track: {start_inventory}. " + str(control.call("looking-at")))

    x, y, z = end
    approach = {
        "xo": (-2 if dx > 0 else 2, 0),
        "zo": (0, -2 if dz > 0 else 2),
        "pd": (-1.5, -1.5),
    }[row["shape"]]
    yaw = {"xo": -90 if dx > 0 else 90, "zo": 0 if dz > 0 else 180, "pd": -45}[row["shape"]]
    command_fn(f"tp {actor} {x + 0.5 + approach[0]} {y} {z + 0.5 + approach[1]} {yaw} 20")
    control.call("wait", 3)
    if dedicated_commands:
        control.call("look-at", x + 0.5, y + 0.06, z + 0.5)
    extended = row["extended"] == "1"
    if extended:
        control.call("key", "ctrl", "down")
        control.call("wait", 2)
    control.call("interact", x, y - 1, z, "up")
    if extended:
        control.call("key", "ctrl", "up")
    control.call("wait", 3)
    if not validate:
        return
    inventory = control.command("/data get entity @s Inventory")
    actual = sum(int(re.search(r"count: (\d+)", slot)[1]) for slot in inventory.split('}, {')
                 if 'id: "create:track"' in slot)
    if actual != remaining:
        raise RuntimeError(f"Case {row['case']} expected {remaining} tracks, read {actual}: {inventory}")
    if not row["segments"]:
        if "create:track_connecting_from" not in inventory:
            raise RuntimeError(f"Case {row['case']} lost its selection after a rejected placement")
        state = control.call("block", *end)["state"]
        if state != "minecraft:air":
            raise RuntimeError(f"Case {row['case']} placed an unsupported curve: {state}")
        return
    if "create:track_connecting_from" in inventory:
        raise RuntimeError(f"Case {row['case']} left the old track selected after placement")

    first, second = (
        add(start, tuple(int(row[f"p{index}_{axis}"]) for axis in "xyz"))
        for index in (1, 2)
    )
    commands = [
        f"/data get block {coordinates(first)} Connections[0].{key}[{index}].{name}"
        for key, name in (("Positions", "Pos"), ("Starts", "V"), ("Axes", "V"))
        for index in (0, 1)
    ]
    commands.append(f"/data get block {coordinates(second)} Connections[0].Positions[1].Pos")
    origin, target, curve_start, curve_end, a, b, inverse = map(vector, control.commands(commands))
    if origin != (0, 0, 0) or add(first, target) != second or add(second, inverse) != first:
        raise RuntimeError(f"Case {row['case']} saved mismatched connection endpoints")

    handle, length, point = geometry((add(first, curve_start), add(first, curve_end)), (a, b))
    if int(length * 2) != int(row["segments"]):
        raise RuntimeError(f"Case {row['case']} expected {row['segments']} track segments, read {int(length * 2)}")
    numeric = [("handle", handle), ("length", length)]
    origin = tuple(-part for part in START)
    for index in range(5):
        numeric.extend((f"q{index}_{axis}", value)
                       for axis, value in zip("xyz", add(point(index / 4), origin), strict=True))
    if offset == (0, 0, 0):
        for name, actual in numeric:
            if abs(actual - float(row[name])) > 0.000002:
                raise RuntimeError(f"Case {row['case']} {name}: Java {row[name]}, Horizon {actual:.8f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/track_curve-java.csv").open() as file:
        reference = list(csv.DictReader(file))
    with fixture_world(args, "Track-curve", STRUCTURE, render=args.visual) as control:
        control.command("/fill -11 111 -24 25 111 7 minecraft:smooth_stone")
        control.command("/gamemode survival")
        # The raised endpoints use an unsupported approach position.
        control.command("/attribute @s minecraft:gravity base set 0")
        for row in reference:
            test_case(control, row)
            if args.visual and row["case"] == "0":
                control.command("/time set noon")
                control.command("/tp @s 4.5 117 0.5")
                control.call("look-at", 12.5, 112.1, -4.5)
                control.call("key", "f1", "tap")
                control.call("wait", 5)
                control.call("screenshot", ROOT / ".local/track-curve.png")
                control.call("key", "f1", "tap")
    print(f"Track curves matched Java placement, geometry, and survival costs in all {len(reference)} cases.")


if __name__ == "__main__":
    main()
