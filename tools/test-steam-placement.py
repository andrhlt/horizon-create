#!/usr/bin/env python3
"""Place a steam engine on a tank and attach its shaft as a player."""

import argparse
from pathlib import Path

from fixture_world import fixture_world

STRUCTURE = Path("gametest/fluids/steam_engine.nbt")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    args = parser.parse_args()
    with fixture_world(args, "Steam-placement", STRUCTURE, render=True) as control:
        control.command("/fill 3 96 -12 9 96 -5 minecraft:smooth_stone")
        control.command("/fill 3 97 -12 9 101 -5 minecraft:air")
        control.command("/setblock 6 97 -10 create:fluid_tank")
        control.command("/tp @s 3.8 97 -9.5 -90 23")
        control.call("wait", 3)
        control.command("/gamemode survival")
        control.commands((
            "/item replace entity @s hotbar.0 with create:steam_engine 1",
            "/item replace entity @s hotbar.1 with create:shaft 1",
        ))
        control.call("select", "create:steam_engine")
        control.call("interact", 6, 97, -10, "west")
        engine = control.call("block", 5, 97, -10)["state"]
        if not engine.startswith("create:steam_engine[") or "face=wall" not in engine or "facing=west" not in engine:
            raise RuntimeError(f"Steam engine did not attach to the tank’s west face: {engine}")

        # Turn the player to favor a north–south shaft across the western output.
        control.command("/tp @s 4.5 97 -7.0 180 15")
        control.call("wait", 3)
        control.call("select", "create:shaft")
        control.call("interact", 5, 97, -10, "south")
        shaft = control.call("block", 3, 97, -10)["state"]
        if not shaft.startswith("create:powered_shaft[") or "axis=z" not in shaft:
            raise RuntimeError(f"The attached powered shaft did not take the north–south axis: {shaft}")
        counts = control.call("inventory")["counts"]
        if counts.get("create:steam_engine", 0) or counts.get("create:shaft", 0):
            raise RuntimeError(f"Placement did not consume the steam engine and shaft: {counts}")
    print("A survival player attached the engine to a tank and installed its powered shaft.")


if __name__ == "__main__":
    main()
