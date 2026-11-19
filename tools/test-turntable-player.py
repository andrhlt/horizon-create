#!/usr/bin/env python3
"""Verify client Turntable yaw and edge motion in an isolated offscreen world."""

import argparse
from contextlib import ExitStack
from importlib import import_module
from math import isclose, sqrt
from pathlib import Path
import struct
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")

GUEST = "TurntableRider"
HOST_TABLE = (9, 171, 21)
GUEST_TABLE = (14, 171, 21)
ENV = {"CREATE_TURNTABLE_PLAYER_TRACE": "1", "HORIZON_NO_AUDIO": "1"}


def f32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def turn(rpm, tick_rate, realtime, partial, x, y, z):
    speed = f32(f32(f32(rpm * f32(2.0 / 3.0)) * f32(tick_rate / 20)) * realtime)
    distance = sqrt(x * x + y * y + z * z)
    if distance > 0.25:
        speed = f32(speed * f32(max(0.0, min(1.0, (0.5 - distance) * 2))))
    return f32(speed * partial)


def set_speed(host, table, rpm):
    x, y, z = table
    host.command(f"/data merge block {x} {y - 1} {z} {{ScrollValue:{rpm}}}")


def matches_position(state, x, y, z):
    return all(isclose(a, b, abs_tol=0.00001, rel_tol=0.0)
               for a, b in zip(state["player"]["position"], (x, y, z), strict=True))


def land(host, actor, player, table):
    x, y, z = table
    host.command(f"/tp {player} {x + 0.5} {y + 0.75} {z + 0.5} 90 0")

    def grounded():
        status = actor.call("state")
        return status["player"]["on_ground"] and matches_position(status, x + 0.5, y + 0.5, z + 0.5)

    multiplayer.until(f"{player} to stand at the center of the Turntable", grounded)


def view_motion(actor, direction, detail):
    start = actor.call("status")["yaw"]

    def turning():
        now = actor.call("status")["yaw"]
        change = (now - start + 180) % 360 - 180
        return direction * change > 0.4

    multiplayer.until(detail, turning, seconds=4)


def exercise(host, actor, player, table):
    set_speed(host, table, 16)
    land(host, actor, player, table)
    view_motion(actor, -1, f"{player} to turn with +16 RPM")
    set_speed(host, table, -16)
    view_motion(actor, 1, f"{player} to turn with -16 RPM")

    x, y, z = table
    host.command(f"/setblock {x} {y - 1} {z} minecraft:air")
    actor.call("wait", 12)
    before = actor.call("status")["yaw"]
    actor.call("wait", 5)
    after = actor.call("status")["yaw"]
    if before != after:
        raise RuntimeError(f"{player} continued rotating after motor removal: {before} -> {after}")

    host.command(f"/setblock {x} {y - 1} {z} create:creative_motor[facing=up]")
    start = host.clock()
    host.step_to(start + 1)
    start_z = z + 0.5
    host.command(f"/tp {player} {x + 1.015} {y + 0.62} {start_z} 90 0")

    def side_push():
        now = actor.call("state")["player"]["position"]
        return now[2] < start_z - 0.015

    multiplayer.until(f"{player} to move tangentially from the east edge", side_push, seconds=4)


def assert_log(path):
    frames = []
    edges = []
    for line in path.read_text().splitlines():
        if line.startswith("CREATE_TURNTABLE_FRAME "):
            frames.append([float(value) for value in line.split(maxsplit=1)[1].split(",")])
        elif line.startswith("CREATE_TURNTABLE_EDGE "):
            edges.append([float(value) for value in line.split(maxsplit=1)[1].split(",")])

    directions = {row[1] for row in frames if row[-2] != row[-1]}
    if not {-16, 16}.issubset(directions):
        raise RuntimeError(f"{path} is missing positive and negative live rotation: {directions}")
    for tick, rpm, tick_rate, realtime, partial, x, y, z, before, after in frames:
        expected = f32(f32(before) - turn(f32(rpm), f32(tick_rate), f32(realtime), f32(partial), x, y, z))
        if f32(after) != expected:
            raise RuntimeError(f"{path} frame at {tick:g}: camera {after}, expected {expected}")

    if not any(rpm == 16 and x >= .5 and after_z < before_z - 0.01
               for _, rpm, x, _, _, _, _, before_z, _, _, after_z in edges):
        raise RuntimeError(f"{path} is missing the powered edge push: {edges[:5]}")
    return len(frames), len(edges)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    name = "TurntablePlayerRideLAN" if args.lan else "TurntablePlayerRide"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, name, render=True, pack=args.pack, env=ENV))
        host.commands((
            "/fill 6 169 18 17 169 25 minecraft:stone",
            "/fill 6 170 18 17 175 25 minecraft:air",
            "/setblock 9 171 21 create:turntable",
            "/setblock 14 171 21 create:turntable",
            "/setblock 9 170 21 create:creative_motor[facing=up]",
            "/setblock 14 170 21 create:creative_motor[facing=up]",
        ))
        host.step_to(host.clock() + 1)
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-turntable-player-")))
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST,
                scenario=name, pack=args.pack, env=ENV, render=True,
            ))
            multiplayer.until("the guest to join", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
        exercise(host, host, "@s", HOST_TABLE)
        if args.lan:
            exercise(host, guest, GUEST, GUEST_TABLE)

    logs = [ROOT / f".local/horizon-{name.lower()}.log"]
    if args.lan:
        logs.append(ROOT / f".local/{name}-{GUEST.lower()}.log")
    for log in logs:
        frames, edges = assert_log(log)
        print(f"{log.name} matched {frames} live camera frames and observed {edges} edge pushes.")
    print("Powered player rotation, reversal, stop and east-edge motion passed.")


if __name__ == "__main__":
    main()
