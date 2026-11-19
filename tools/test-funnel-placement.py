#!/usr/bin/env python3
"""Place a brass funnel through the player and feed sand onto its belt."""

import argparse
from pathlib import Path

from fixture_world import fixture_world

STRUCTURE = Path("gametest/processing/sand_washing.nbt")


def run(args):
    with fixture_world(args, "Funnel-placement", STRUCTURE, render=True) as control:
        control.commands((
            "/place template create:gametest/processing/sand_washing 3 96 -12",
            "/setblock 8 98 -10 minecraft:air",
            "/setblock 8 98 -11 minecraft:lever[face=floor,facing=south,powered=false]",
            "/item replace entity @s hotbar.0 with create:brass_funnel",
            "/tp @s 8.55 100 -8.60 180 76",
        ))
        # The server uses the player's synchronized facing for top-face placement.
        control.step_to(control.clock() + 1)
        control.call("look-at", 8.5, 97.82, -9.5)
        control.call("select", "create:brass_funnel")
        control.call("interact", 8, 97, -10, "up")
        funnel = control.call("block", 8, 98, -10)["state"]
        if not all(part in funnel for part in ("create:brass_belt_funnel[", "facing=north", "shape=pushing")):
            raise RuntimeError(f"Placement did not produce a north-facing pushing funnel: {funnel}")
        control.step_to(control.clock() + 1)
        inventory = control.command("/data get block 10 97 -10 Inventory")
        if 'id: "minecraft:sand"' not in inventory or "count: 64" not in inventory:
            raise RuntimeError(f"The placed funnel did not feed a stack of sand onto the belt: {inventory}")
    print("The placed brass funnel pushed a stack of sand from the crate onto the belt.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())


if __name__ == "__main__":
    main()
