#!/usr/bin/env python3
"""Check Creative Crate filter persistence and continued bottomless supply."""
import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

CRATE = (9, 171, 22)
FILTER = 'minecraft:iron_ingot[minecraft:custom_data={marker:17}]'
mp = import_module("test-multiplayer")


def crate_data(control):
    return control.command(f"/data get block {' '.join(map(str, CRATE))}")


def has_tagged_filter(control):
    data = crate_data(control)
    return data if '"minecraft:iron_ingot"' in data and "marker: 17" in data else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    args = parser.parse_args()

    with fixture_world(args, "CreativeCratePersistence", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as control:
        control.commands((
            "/gamemode survival @s",
            "/fill 5 169 17 15 169 27 minecraft:stone",
            "/fill 5 170 17 15 175 27 minecraft:air",
            "/setblock 9 170 24 minecraft:stone",
            f"/setblock {' '.join(map(str, CRATE))} create:creative_crate",
            "/tp @s 9.5 171 24.5",
            f"/item replace entity @s hotbar.0 with {FILTER} 7",
        ))
        mp.until("tagged iron reaches the player's inventory",
                 lambda: mp.count(control, "minecraft:iron_ingot") == 7)
        control.call("select", "minecraft:iron_ingot")
        control.call("look-at", 9.5, 172, 22.5)
        mp.until("the crate value box to be targeted",
                 lambda: (hit := control.call("looking-at").get("block"))
                 and hit["pos"] == list(CRATE) and hit["face"] == "up")
        control.call("mouse", "right", "click")
        mp.until("the tagged filter to be installed", lambda: has_tagged_filter(control))
        filter_before = crate_data(control)

        control.command("/save-all")
        control.restart()
        filter_after = crate_data(control)
        if '"minecraft:iron_ingot"' not in filter_after or "marker: 17" not in filter_after:
            raise AssertionError(f"Configured filter changed after reopen: {filter_before} -> {filter_after}")

        control.commands((
            "/setblock 9 170 22 minecraft:hopper[facing=down] strict",
            "/setblock 9 169 22 minecraft:chest",
        ))
        start = control.clock()
        for tick in range(1, 41):
            control.step_to(start + tick)
        hopper = control.command("/data get block 9 170 22 Items")
        chest = control.command("/data get block 9 169 22 Items")
        if '"minecraft:iron_ingot"' not in hopper and '"minecraft:iron_ingot"' not in chest:
            raise AssertionError(f"Reopened crate stopped supplying its filter item: {hopper} / {chest}")
        if "marker: 17" not in hopper and "marker: 17" not in chest:
            raise AssertionError(f"Reopened crate did not supply the filtered components: {hopper} / {chest}")
        filter_final = crate_data(control)
        if '"minecraft:iron_ingot"' not in filter_final or "marker: 17" not in filter_final:
            raise AssertionError(f"Extraction changed the crate filter: {filter_final}")
    print("Tagged Creative Crate filter survived save/reopen; Hopper extraction resumed with components intact.")


if __name__ == "__main__":
    main()
