#!/usr/bin/env python3
"""Compare survival two-click track placement with the Java line trace."""

import argparse
import csv
import re
from pathlib import Path

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/track_crafting.nbt")
START = (12, 105, -12)


def kind(dx, dz):
    if dx == 0:
        return "zo"
    if dz == 0:
        return "xo"
    return "pd" if dx == dz else "nd"


def run(args):
    with (ROOT / "fixtures/track_line-java.csv").open() as file:
        reference = list(csv.DictReader(file))
    with fixture_world(args, "Track-line", STRUCTURE) as control:
        control.commands((
            "/fill 6 104 -16 22 104 -4 minecraft:smooth_stone",
            "/gamemode survival",
        ))
        for row in reference:
            dx, dz, length, existing, obstacle, supplied, remaining = (
                int(row[key]) for key in ("dx", "dz", "length", "existing",
                                          "obstacle", "supplied", "remaining")
            )
            x, y, z = START
            end = (x + dx * length, y, z + dz * length)
            shape = kind(dx, dz)
            yaw = row["yaw"]
            control.commands((
                f"/fill 6 {y} -16 22 {y + 2} -4 minecraft:air",
                f"/setblock {x} {y} {z} create:track[shape={shape}]",
                f"/tp @s {x + 0.5 - dx * 2} {y} {z + 0.5 - dz * 2} {yaw} 20",
                f"/item replace entity @s hotbar.0 with create:track {supplied}",
            ))
            if existing:
                control.command(f"/setblock {end[0]} {y} {end[2]} create:track[shape={shape}]")
            if obstacle in (1, 2):
                block = "minecraft:stone" if obstacle == 1 else "create:track[shape=zo]"
                control.command(f"/setblock {x + 3 * dx} {y} {z + 3 * dz} {block}")
            control.call("wait", 3)
            control.call("select", "create:track")
            control.call("look-at", x + 0.5, y + 0.06, z + 0.5)
            control.call("mouse", "right", "click")

            target = end if existing else (end[0], y - 1, end[2])
            control.command(
                f"/tp @s {end[0] + 0.5 + dx * 2} {y} {end[2] + 0.5 + dz * 2} {yaw} 20"
            )
            control.call("wait", 3)
            if existing:
                control.call("look-at", end[0] + 0.5, y + 0.06, end[2] + 0.5)
                control.call("mouse", "right", "click")
            else:
                control.call("interact", *target, "up")
            control.call("wait", 3)

            for step, block in enumerate(row["states"].split(";")):
                at = (x + dx * step, y, z + dz * step)
                expected = {"-": "minecraft:air", "stone": "minecraft:stone"}.get(
                    block, f"create:track[shape={block}]"
                )
                result = control.call(
                    "command", f"/execute if block {at[0]} {at[1]} {at[2]} {expected} run say track match"
                )
                if not any("track match" in line for line in result.get("chat") or []):
                    raise RuntimeError(f"Case {row['case']} at {at}: expected {expected}, actual "
                                       f"{control.call('block', *at)['state']}")
            inventory = control.command("/data get entity @s Inventory")
            actual = sum(int(re.search(r"count: (\d+)", slot)[1])
                         for slot in inventory.split('}, {')
                         if 'id: "create:track"' in slot)
            if actual != remaining:
                raise RuntimeError(f"Case {row['case']} expected {remaining} tracks, read {actual}: {inventory}")

    print(f"Java matched track shapes and survival costs in all {len(reference)} line placements.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())


if __name__ == "__main__":
    main()
