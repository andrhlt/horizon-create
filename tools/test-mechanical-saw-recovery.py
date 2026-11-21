#!/usr/bin/env python3
"""Verify a Mechanical Saw retains and delivers output after a full Depot clears."""

import argparse
from pathlib import Path

from fixture_world import fixture_world


SAW = (8, 180, 8)
DEPOT = (9, 180, 8)


def xyz(pos):
    return " ".join(map(str, pos))


def run(args):
    with fixture_world(args, "MechanicalSawOutputRecovery", pack=args.pack) as control:
        control.commands((
            "/fill 5 179 3 14 179 12 minecraft:smooth_stone",
            f"/setblock {xyz(SAW)} create:mechanical_saw[facing=up]",
            f"/setblock {xyz(DEPOT)} create:depot",
            "/setblock 8 180 7 create:creative_motor[facing=south]{ScrollValue:96}",
            f"/data merge block {xyz(SAW)} {{Filter:{{id:\"minecraft:bamboo_mosaic\",count:1}}}}",
            f"/data merge block {xyz(DEPOT)} {{Items:[{{Slot:0b,id:\"minecraft:cobblestone\",count:64}}]}}",
            '/summon minecraft:item 8.5 180.79 8.5 {Item:{id:"minecraft:bamboo_planks",count:1},Motion:[0.0d,0.0d,0.0d]}',
            "/tp @s 8.5 182 11.5",
        ))
        for _ in range(32):
            control.step_to(control.clock() + 1)
        blocked = control.command(f"/data get block {xyz(SAW)} Items")
        if "minecraft:bamboo_mosaic" not in blocked:
            raise RuntimeError(f"Full Depot did not leave saw output buffered: {blocked}")
        control.command(f"/data merge block {xyz(DEPOT)} {{Items:[]}}")
        for _ in range(3):
            control.step_to(control.clock() + 1)
        recovered = control.command(f"/data get block {xyz(DEPOT)} Items")
        if "minecraft:bamboo_mosaic" not in recovered:
            raise RuntimeError(f"Saw did not deliver buffered output after Depot cleared: {recovered}")
        remaining = control.command(f"/data get block {xyz(SAW)} Items")
        if "minecraft:bamboo_mosaic" in remaining:
            raise RuntimeError(f"Saw retained output after Depot accepted it: {remaining}")
    print("Mechanical Saw retained output against a full Depot and delivered it after recovery.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
