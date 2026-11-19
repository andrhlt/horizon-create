#!/usr/bin/env python3
"""Place original track items as a player and check Java's placed shapes."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/track_crafting.nbt")
FLOOR = (8, 104, -8)
POSITION = (8, 105, -8)
STEPS = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}


def run(args):
    csv_path = ROOT / "fixtures/track_placement-java.csv"
    with csv_path.open() as file:
        expected = list(csv.DictReader(file))
    with fixture_world(args, "Track-placement", STRUCTURE, render=args.visual) as control:
        control.commands((
            "/fill 4 104 -13 13 104 -4 minecraft:smooth_stone",
            "/fill 4 105 -13 13 110 -4 minecraft:air",
            "/tp @s 8.5 105 -10.2 180 20",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:track 15",
        ))
        control.call("wait", 4)
        control.call("select", "create:track")
        for row in expected:
            yaw, pitch = row["yaw"], row["pitch"]
            for dx, dz in STEPS.values():
                control.command(f"/setblock {POSITION[0]+dx} {POSITION[1]} {POSITION[2]+dz} minecraft:air")
            if row["step"] in STEPS:
                dx, dz = STEPS[row["step"]]
                control.command(f"/setblock {POSITION[0]+dx} {POSITION[1]} {POSITION[2]+dz} minecraft:stone")
            # Select the spot independently of the look direction, as the
            # Java trace does when it creates its block hit result.
            player_z = -5.8 if row['step'] == "north" else -10.2
            control.command(f"/tp @s 8.5 105 {player_z} {yaw} {pitch}")
            control.call("wait", 2)
            control.call("interact", *FLOOR, "up")
            x, y, z = POSITION
            reference = row["shape"]
            check = control.command(f"/execute if block {x} {y} {z} create:track[shape={reference}] run say Java shape")
            if "Java shape" not in check:
                observed = control.call("block", *POSITION)["state"]
                raise RuntimeError(f"Case {row['case']} expected Java shape {reference}, read {observed}")
            if args.visual and row["case"] in ("0", "2", "8"):
                control.command("/time set noon")
                control.call("look-at", x + 0.5, y + 0.2, z + 0.5)
                control.call("key", "f1", "tap")
                control.call("wait", 3)
                control.call("screenshot", ROOT / f".local/track-placement-{row['case']}.png")
                control.call("key", "f1", "tap")
            control.command(f"/setblock {x} {y} {z} minecraft:air")
        remaining = control.call("inventory")["counts"].get("create:track", 0)
        if remaining:
            raise RuntimeError(f"Did not consume a track for each placement. Remaining {remaining}.")
    print(f"Java matched all {len(expected)} track placements through normal survival clicks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--visual", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
