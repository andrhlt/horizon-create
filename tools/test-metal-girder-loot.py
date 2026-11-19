#!/usr/bin/env python3
"""Compare ordinary dry and wet plain Girder drops to the original loot table."""
import argparse
from pathlib import Path

from fixture_world import fixture_world

GIRDER = "create:metal_girder"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with fixture_world(args, "MetalGirderLoot", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 4 100 -15 15 100 -5 minecraft:smooth_stone",
            "/fill 4 101 -15 15 103 -5 minecraft:air",
            "/tp @s 11.500 101 -9.500",
            "/gamemode survival",
        ))
        for index, wet in enumerate(("false", "true"), start=1):
            control.command(f"/setblock 8 101 -10 {GIRDER}[axis=x,x=true,waterlogged={wet}]")
            control.command("/setblock 8 101 -10 minecraft:air destroy")
            control.step_to(control.clock() + 1)
            items = control.call("entities", 12, "minecraft:item")["entities"]
            count = sum(entity["item"]["count"] for entity in items if entity["item"]["item"] == GIRDER)
            if count != index:
                raise RuntimeError(f"Expected {index} dropped girders after wet={wet}, got {count}")
    print("Dry and waterlogged ordinary destruction each dropped one Java Metal Girder.")


if __name__ == "__main__":
    main()
