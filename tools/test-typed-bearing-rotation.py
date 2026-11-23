#!/usr/bin/env python3
"""Exercise one powered, glued bearing rotation with a standing rider."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world

BEARING = (0, 100, 0)
MOTOR = (0, 99, 0)
CHEST = (1, 101, 0)


def xyz(pos):
    return " ".join(map(str, pos))


def block_data(control, pos):
    return control.command(f"/data get block {xyz(pos)}")


def number(data, key):
    match = re.search(rf"\b{re.escape(key)}: (-?\d+(?:\.\d+)?)(?:[fd])?", data)
    return float(match.group(1)) if match else None


def payload_pos(data):
    match = re.search(r"PayloadPos: \[I; (-?\d+), (-?\d+), (-?\d+)\]", data)
    return tuple(map(int, match.groups())) if match else None


def carried_items(control, pos):
    data = block_data(control, pos)
    return sum(map(int, re.findall(r"count: (\d+)", data)))


def player_position(control):
    return tuple(control.call("state")["player"]["position"][:3])


def close(actual, expected, tolerance=0.3):
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))


def advance(control, ticks):
    for _ in range(ticks):
        control.step_to(control.clock() + 1)


def setup(control, *, blocked=False):
    commands = [
        "/fill -3 97 -3 3 105 3 minecraft:air",
        f"/setblock {xyz(BEARING)} create:mechanical_bearing[facing=up]",
        f"/setblock {xyz(MOTOR)} create:creative_motor[facing=up]{{ScrollValue:20}}",
        f"/setblock {xyz(CHEST)} minecraft:chest",
        f"/item replace block {xyz(CHEST)} container.0 with minecraft:iron_ingot 7",
        "/tp @s 1.5 102 0.5",
    ]
    if blocked:
        commands.insert(4, "/setblock 0 101 -1 minecraft:stone")
    control.commands(tuple(commands))


def verify(args):
    with fixture_world(args, "TypedBearingRotation", pack=args.pack) as control:
        setup(control)
        advance(control, 15)
        active = block_data(control, BEARING)
        rotated = payload_pos(active)
        angle = number(active, "Angle")
        if angle is None or abs(angle - 90.0) > 8.0:
            raise RuntimeError(f"Powered bearing did not accumulate source-matched angle: {active}")
        if rotated is None or rotated == CHEST or number(active, "RiderCaptured") != 1:
            raise RuntimeError(f"Powered bearing did not rotate/capture glued payload: {active}")
        if carried_items(control, rotated) != 7:
            raise RuntimeError("Rotated chest inventory was not conserved.")
        expected_rider = (0.5, 102.0, -0.5)
        rider = player_position(control)
        if not close(rider, expected_rider):
            raise RuntimeError(f"Rider did not follow the powered bearing transform: {rider} != {expected_rider}")

        saved_offset = number(active, "MotionOffset")
        control.call("save")
        control.restart()
        reopened = block_data(control, BEARING)
        reopened_pos = payload_pos(reopened)
        reopened_angle = number(reopened, "Angle")
        reopened_offset = number(reopened, "MotionOffset")
        if reopened_pos is None or carried_items(control, reopened_pos) != 7:
            raise RuntimeError(f"Rotated payload did not survive reopen: {reopened}")
        # fixture_world freezes after launch; measure the ticks that happened
        # before that freeze using the Part's persisted motion counter. The
        # world clock also advances during startup, but not every world tick
        # runs this block entity Part.
        motion_ticks = max(0, (reopened_offset or 0) - (saved_offset or 0))
        expected_reopened_angle = angle + motion_ticks * 6.0
        if reopened_angle is None or reopened_angle < angle or abs(reopened_angle - expected_reopened_angle) > 8.0:
            raise RuntimeError(
                f"Powered bearing angle did not preserve measured reload continuity "
                f"({motion_ticks} Part ticks, expected {expected_reopened_angle}): {reopened}"
            )

        control.command(f"/data merge block {xyz(MOTOR)} {{ScrollValue:0}}")
        advance(control, 1)
        finished = block_data(control, BEARING)
        if number(finished, "Moving") != 0 or number(finished, "RiderSafeDismount") != 1:
            raise RuntimeError(f"Rotated bearing did not dismount safely: {finished}")
        if carried_items(control, reopened_pos) != 7:
            raise RuntimeError("Rotated chest inventory was not conserved at dismount.")

    with fixture_world(args, "TypedBearingRotationBlocked", pack=args.pack) as control:
        setup(control, blocked=True)
        advance(control, 15)
        blocked = block_data(control, BEARING)
        blocked_pos = payload_pos(blocked)
        if number(blocked, "CollisionBlocked") != 1 or number(blocked, "Moving") != 0:
            raise RuntimeError(f"Powered bearing ignored a solid target collision: {blocked}")
        if number(blocked, "RiderSafeDismount") != 1:
            raise RuntimeError(f"Blocked bearing did not safely dismount its rider: {blocked}")
        if blocked_pos is None or carried_items(control, blocked_pos) != 7:
            raise RuntimeError("Blocked bearing did not conserve the payload inventory.")
    print("Powered bearing rotated a glued chest, carried a rider, survived reopen, and dismounted safely.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
