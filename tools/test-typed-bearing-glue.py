#!/usr/bin/env python3
"""Exercise one real super-glue marker beyond the seed payload ring."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world

BEARING = (0, 100, 0)
MOTOR = (0, 99, 0)
CHEST = (1, 101, 0)
EXTENSION = (2, 101, 0)


def xyz(pos):
    return " ".join(map(str, pos))


def data(control, pos):
    return control.command(f"/data get block {xyz(pos)}")


def number(reply, key):
    match = re.search(rf"\b{re.escape(key)}: (-?\d+(?:\.\d+)?)(?:[bslfd])?", reply)
    return float(match.group(1)) if match else None


def positions(reply):
    match = re.search(r"PayloadPositions: \[(.*?)\], x:", reply)
    return [tuple(map(int, values)) for values in re.findall(
        r"\[I; (-?\d+), (-?\d+), (-?\d+)\]", match.group(1)
    )] if match else []


def items(control, pos):
    return sum(map(int, re.findall(r"count: (\d+)", data(control, pos))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with fixture_world(args, "TypedBearingGlue", pack=args.pack) as control:
        control.commands((
            "/fill -3 97 -3 4 105 3 minecraft:air",
            f"/summon minecraft:marker 0 101 0 {{CreateSuperGlue:1b,From:[0d,0d,-1d],To:[3d,1d,2d]}}",
            f"/setblock {xyz(BEARING)} create:mechanical_bearing[facing=up]",
            f"/setblock {xyz(MOTOR)} create:creative_motor[facing=up]{{ScrollValue:20}}",
            f"/setblock {xyz(CHEST)} minecraft:chest",
            f"/setblock {xyz(EXTENSION)} minecraft:barrel[facing=north]",
            f"/item replace block {xyz(CHEST)} container.0 with minecraft:iron_ingot 7",
            "/tp @s 1.5 102 0.5",
        ))
        marker = control.command("/data get entity @e[type=minecraft:marker,limit=1]")
        if "CreateSuperGlue: 1b" not in marker:
            raise RuntimeError(f"Glue marker fixture was not created: {marker}")
        for _ in range(15):
            control.step_to(control.clock() + 1)
        active = data(control, BEARING)
        carried = positions(active)
        if number(active, "Angle") is None or number(active, "Angle") < 80:
            raise RuntimeError(f"Powered glued bearing did not rotate: {active}")
        if len(carried) != 2 or EXTENSION in carried:
            raise RuntimeError(f"Special-entity glue traversal missed the extension: {active}")
        if sorted(items(control, position) for position in carried) != [0, 7]:
            raise RuntimeError(f"Glued payload inventory was not conserved: {active}")
        saved_angle = number(active, "Angle")
        control.command("/save-all flush")
        control.restart()
        reopened = data(control, BEARING)
        reopened_positions = positions(reopened)
        reopened_angle = number(reopened, "Angle")
        if reopened_angle is None or saved_angle is None or reopened_angle < saved_angle:
            raise RuntimeError(f"Glued bearing state did not survive save/reopen: {reopened}")
        if len(reopened_positions) != 2 or sorted(items(control, position) for position in reopened_positions) != [0, 7]:
            raise RuntimeError(f"Glued payload was not restored with inventory after reopen: {reopened}")
        control.command(f"/data merge block {xyz(MOTOR)} {{ScrollValue:0}}")
        control.step_to(control.clock() + 1)
        stopped = data(control, BEARING)
        if "Moving: 0b" not in stopped or sorted(items(control, position) for position in positions(stopped)) != [0, 7]:
            raise RuntimeError(f"Glued payload did not disassemble safely: {stopped}")
    print("Super-glue traversal carried the extension and disassembled with seven ingots conserved.")


if __name__ == "__main__":
    main()
