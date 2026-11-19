#!/usr/bin/env python3
"""Verify dry and wet Copper and dyed Valve supports and drops at the action tick."""
import argparse
import csv
from pathlib import Path

from fixture_world import ROOT, fixture_world



def coord(pos):
    return " ".join(map(str, pos))


def displacement(pos, normal, sign):
    return tuple(p + sign * d for p, d in zip(pos, normal, strict=True))


def item_count(control, pos, valve):
    return sum(
        found["item"]["count"]
        for found in control.call("entities", 12, "minecraft:item")["entities"]
        if found["item"]["item"] == valve
        and all(abs(axis - cell - 0.5) < 1.5 for axis, cell in zip(found["pos"], pos, strict=True))
    )


def verify(args):
    with (ROOT / "fixtures/valve-support-removal-java.csv").open() as source:
        _, *rows = csv.reader(source)
    if len(rows) != 3:
        raise RuntimeError(f"The Java fixture should have three support-removal cases, got {len(rows)}.")
    with fixture_world(args, "ValveSupportRemoval", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 4 100 -24 14 100 -5 minecraft:smooth_stone",
            "/fill 4 101 -23 14 105 -6 minecraft:air",
            "/gamemode survival",
        ))
        for _, case, valve, removed, fluid, expected_drops in rows:
            index = int(case)
            pos = (8, 101, -10 - 4 * index)
            face = "south" if index == 2 else "east"
            normal = (0, 0, 1) if face == "south" else (1, 0, 0)
            rear = displacement(pos, normal, -1)
            front = displacement(pos, normal, 1)
            waterlogged = "true" if int(fluid) else "false"
            block = f"{valve}[facing={face},waterlogged={waterlogged}]"
            control.commands((
                f"/tp @s 11.500 101.000 {pos[2] + 0.5}",
                f"/setblock {coord(rear)} minecraft:stone",
                f"/setblock {coord(front)} minecraft:stone",
                f"/setblock {coord(pos)} {block}",
            ))
            control.step_to(control.clock() + 1)
            action_time = control.clock()
            control.command(f"/setblock {coord(front)} minecraft:air")
            if control.call("block", *pos)["state"] != block or item_count(control, pos, valve):
                raise RuntimeError(f"Removing a front block should leave {block} intact.")
            control.command(f"/setblock {coord(rear)} minecraft:air")
            control.call("wait", 3)
            state = control.call("block", *pos)
            actual_fluid = 8 if state["state"] == "minecraft:water[level=0]" else 0
            actual = (state["block"], actual_fluid, item_count(control, pos, valve))
            expected = (removed, int(fluid), int(expected_drops))
            if actual != expected or control.clock() != action_time:
                raise RuntimeError(f"Valve support case {index} gave {actual} expected {expected} on the action tick.")
    print("Three Valve supports match Java's immediate drop and source-water restoration; front changes retain all three.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
