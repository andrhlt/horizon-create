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


def advance(control, ticks):
    for _ in range(ticks):
        control.step_to(control.clock() + 1)


def verify(args):
    with fixture_world(args, "TypedBearingRotation", pack=args.pack) as control:
        control.commands((
            "/fill -3 97 -3 3 105 3 minecraft:air",
            f"/setblock {xyz(BEARING)} create:mechanical_bearing[facing=up]",
            f"/setblock {xyz(MOTOR)} create:creative_motor[facing=up]{{ScrollValue:20}}",
            f"/setblock {xyz(CHEST)} minecraft:chest",
            f"/item replace block {xyz(CHEST)} container.0 with minecraft:iron_ingot 7",
            "/tp @s 1.5 102 0.5",
        ))
        advance(control, 15)
        active = block_data(control, BEARING)
        rotated = payload_pos(active)
        if number(active, "Angle") is None or number(active, "Angle") <= 60:
            raise RuntimeError(f"Powered bearing did not accumulate source-matched angle: {active}")
        if rotated is None or rotated == CHEST or number(active, "RiderCaptured") != 1:
            raise RuntimeError(f"Powered bearing did not rotate/capture glued payload: {active}")
        if carried_items(control, rotated) != 7:
            raise RuntimeError("Rotated chest inventory was not conserved.")

        control.call("save")
        control.restart()
        reopened = block_data(control, BEARING)
        reopened_pos = payload_pos(reopened)
        if reopened_pos is None or carried_items(control, reopened_pos) != 7:
            raise RuntimeError(f"Rotated payload did not survive reopen: {reopened}")

        control.command(f"/data merge block {xyz(MOTOR)} {{ScrollValue:0}}")
        advance(control, 1)
        finished = block_data(control, BEARING)
        if number(finished, "Moving") != 0 or number(finished, "RiderSafeDismount") != 1:
            raise RuntimeError(f"Rotated bearing did not dismount safely: {finished}")
        if carried_items(control, reopened_pos) != 7:
            raise RuntimeError("Rotated chest inventory was not conserved at dismount.")
    print("Powered bearing rotated a glued chest, carried a rider, survived reopen, and dismounted safely.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
