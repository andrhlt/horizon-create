#!/usr/bin/env python3
"""Place a Packager beside a stocked Barrel and verify survival transfer."""

import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

packager = import_module("test-packager-redstone")
MACHINE = (8, 105, -12)
BARREL = (7, 105, -12)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()

    with fixture_world(args, "PackagerSurvivalPlacement", pack=args.pack) as world:
        world.commands((
            "/fill 5 104 -15 13 104 -9 minecraft:smooth_stone",
            "/fill 5 105 -15 13 109 -9 minecraft:air",
            f"/setblock {packager.xyz(BARREL)} minecraft:barrel",
            f"/setblock {packager.xyz((8, 105, -13))} minecraft:oak_sign",
            f'/data merge block 8 105 -13 {{front_text:{{messages:[{{text:"Warehouse"}},{{text:"A"}},{{text:""}},{{text:""}}]}}}}',
            f"/item replace block {packager.xyz(BARREL)} container.0 with minecraft:iron_ingot 5",
            f"/item replace block {packager.xyz(BARREL)} container.3 with minecraft:redstone 2",
            "/gamemode survival",
            "/tp @s 10.5 105 -11.5",
            "/item replace entity @s hotbar.0 with create:packager",
        ))
        world.call("wait", 3)
        world.call("select", "create:packager")
        world.call("interact", 8, 104, -12, "up")
        placed = world.call("block", *MACHINE)["state"]
        assert "facing=east" in placed, placed

        world.command("/setblock 8 105 -11 minecraft:redstone_block")
        state = packager.block_data(world, MACHINE)
        barrel = packager.block_value(world, BARREL, "Items")
        assert "HeldBox:" in state, state
        assert packager.string(state, "SignAddress") == "Warehouse A", state
        payload = packager.block_value(
            world, MACHINE, 'HeldBox.components."create:package_contents"'
        )
        contents = packager.describe_slots(payload, "slot")
        assert contents == "0:minecraft:iron_ingot=5|1:minecraft:redstone=2", contents
        assert not packager.describe_slots(barrel, "Slot"), barrel
        print("Survival placement faced the stocked Barrel; the redstone pulse sent five iron and two redstone with its sign address.")


if __name__ == "__main__":
    main()
