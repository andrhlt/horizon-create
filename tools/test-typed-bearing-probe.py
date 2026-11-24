#!/usr/bin/env python3
"""Exercise the bounded typed bearing payload/rider adapter in a real world."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world

BEARING = (0, 100, 0)
CHEST = (0, 101, 0)


def xyz(pos):
    return " ".join(map(str, pos))


def block_data(control, pos):
    return control.command(f"/data get block {xyz(pos)}")


def number(data, key):
    match = re.search(rf"\b{re.escape(key)}: (-?\d+)", data)
    return int(match.group(1)) if match else None


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
    with fixture_world(args, "TypedBearingProbe", pack=args.pack) as control:
        control.commands((
            "/fill -2 99 -2 2 112 2 minecraft:air",
            f"/setblock {xyz(BEARING)} create:mechanical_bearing[facing=up]",
            f"/setblock {xyz(CHEST)} minecraft:chest",
            f"/item replace block {xyz(CHEST)} container.0 with minecraft:iron_ingot 7",
            "/tp @s 0.5 102 0.5",
        ))
        advance(control, 3)
        active = block_data(control, BEARING)
        if payload_pos(active) != (0, 104, 0) or number(active, "RiderCaptured") != 1:
            rider = control.command("/data get entity @s Pos")
            raise RuntimeError(f"Payload/rider did not advance three blocks: {active}; rider={rider}")
        if carried_items(control, (0, 104, 0)) != 7:
            raise RuntimeError("The chest inventory was not conserved during movement.")

        control.call("save")
        control.restart()
        reopened = block_data(control, BEARING)
        reopened_pos = payload_pos(reopened)
        # The server may tick once during its startup before the harness freezes
        # it again, so accept any persisted position through the bounded run.
        if reopened_pos is None or not 104 <= reopened_pos[1] <= 109:
            raise RuntimeError(f"Payload position did not survive reopen: {reopened}")
        if carried_items(control, reopened_pos) != 7:
            raise RuntimeError("The reopened moving chest lost its inventory.")

        advance(control, 6)
        finished = block_data(control, BEARING)
        if number(finished, "Moving") != 0 or number(finished, "Disassembled") != 1:
            raise RuntimeError(f"Payload did not reach its safe terminal state: {finished}")
        if number(finished, "RiderSafeDismount") != 1:
            raise RuntimeError(f"Rider did not receive a terminal dismount: {finished}")
        if control.call("block", 0, 109, 0)["block"] != "minecraft:chest":
            raise RuntimeError("The chest was not restored at its final payload position.")
        if carried_items(control, (0, 109, 0)) != 7:
            raise RuntimeError("The disassembled chest inventory was not conserved.")
    print("Typed bearing moved a seven-ingot chest, carried a rider, survived an active reopen, and dismounted safely.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
