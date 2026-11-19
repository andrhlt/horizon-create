#!/usr/bin/env python3
"""Bind train stations with actual survival clicks and compare Java's target data."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/misc/threshold_switch_pulley.nbt")
X, Y, Z = 9, 112, -8


def run(args):
    with (ROOT / "fixtures/track_station-java.csv").open() as file:
        expected = list(csv.DictReader(file))
    with fixture_world(args, "Track-station", STRUCTURE, pack=args.pack) as control:
        control.commands((
            f"/fill -2 {Y-1} {Z-4} 25 {Y-1} {Z+18} minecraft:smooth_stone",
            f"/fill {X-8} {Y} {Z} {X+14} {Y} {Z} create:track[shape=xo]",
            f"/setblock {X-1} {Y} {Z} create:track[shape=cr_o]",
            "/gamemode survival",
        ))
        for row in expected:
            x = X + int(row["dx"])
            z = Z + int(row["distance"])
            sign = 1 if row["reverse"] == "1" else -1
            yaw = 90 * sign
            control.command("/item replace entity @s hotbar.0 with create:track_station 2")
            control.call("wait", 2)
            control.call("key", "1", "tap")
            if row["select"] == "1":
                control.command(f"/tp @s {x + 0.5 + sign * 2} {Y} {Z+0.5} {yaw} 20")
                control.call("wait", 2)
                control.call("look-at", x + 0.5, Y + 0.06, Z + 0.5)
                control.call("mouse", "right", "click")
                control.call("wait", 3)
            selected = control.command("/data get entity @s Inventory")
            actual = int("create:track_targeting_item_selected_pos" in selected)
            if actual != int(row["selected"]):
                raise RuntimeError(f"Case {row['case']} expected selection={row['selected']}, got {actual}: {selected}")

            control.command(f"/tp @s {x+0.5} {Y} {z+2.5} 180 20")
            control.call("wait", 2)
            control.call("interact", x, Y - 1, z, "up")
            control.call("wait", 3)
            inventory = control.command("/data get entity @s Inventory")
            remaining = re.search(r"\bcount: (\d+)", inventory)
            if not remaining or remaining[1] != row["remaining"]:
                raise RuntimeError(f"Case {row['case']} expected {row['remaining']} stations, read {inventory}")
            block = control.call("block", x, Y, z)["block"]
            if row["remaining"] == "2":
                if block != "minecraft:air":
                    raise RuntimeError(f"Case {row['case']} unexpectedly placed {block}")
                continue

            if block != "create:track_station":
                raise RuntimeError(f"Case {row['case']} had no station at the destination: {block}")
            if "create:track_targeting_item_selected_pos" in inventory:
                raise RuntimeError(f"Case {row['case']} left a selected track on the remaining item")
            pos, direction = control.commands((
                f"/data get block {x} {Y} {z} TargetTrack",
                f"/data get block {x} {Y} {z} TargetDirection",
            ))
            found = re.search(r"\[I; (-?\d+), (-?\d+), (-?\d+)\]", pos)
            wanted = tuple(row[f"target_{axis}"] for axis in "xyz")
            if not found or found.groups() != wanted or not direction.endswith(row["target_direction"] + "b"):
                raise RuntimeError(f"Case {row['case']} expected target {wanted}, direction "
                                   f"{row['target_direction']}; read {pos}, {direction}")
    print(f"All {len(expected)} Train Station targeting and placement cases matched Java.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())


if __name__ == "__main__":
    main()
