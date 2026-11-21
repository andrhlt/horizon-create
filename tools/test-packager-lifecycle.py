#!/usr/bin/env python3
"""Check Packager idle/active reopen and atomic full-target unpacking."""

import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")
packager = import_module("test-packager-redstone")
MACHINE = (8, 105, -12)
BARREL = (7, 105, -12)
POWER = (8, 105, -11)


def contents(world):
    serialized = packager.block_value(
        world, MACHINE, 'HeldBox.components."create:package_contents"'
    )
    return packager.describe_slots(serialized, "slot")


def click(world):
    packager.click(world, world)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()

    with fixture_world(args, "PackagerLifecycle", render=True, pack=args.pack) as world:
        world.commands((
            "/fill 5 104 -15 13 104 -9 minecraft:smooth_stone",
            "/fill 5 105 -15 13 109 -9 minecraft:air",
            f"/setblock {packager.xyz(BARREL)} minecraft:barrel",
            f"/setblock {packager.xyz(MACHINE)} create:packager[facing=east]",
            f"/setblock 8 105 -13 minecraft:oak_sign",
            '/data merge block 8 105 -13 {front_text:{messages:[{text:"Warehouse"},{text:"A"},{text:""},{text:""}]}}',
            f"/item replace block {packager.xyz(BARREL)} container.0 with minecraft:iron_ingot 5",
            f"/item replace block {packager.xyz(BARREL)} container.3 with minecraft:redstone 2",
            "/tp @s 10.5 105 -11.5",
        ))

        # Idle contents and attachment survive a cold world reopen.
        world.call("save")
        world.restart()
        idle_state = world.call("block", *MACHINE)["state"]
        idle_barrel = packager.block_value(world, BARREL, "Items")
        assert "facing=east" in idle_state, idle_state
        assert packager.describe_slots(idle_barrel, "Slot") == (
            "0:minecraft:iron_ingot=5|3:minecraft:redstone=2"
        ), idle_barrel

        # The active held parcel and its source deduction survive reopen.
        world.command(f"/setblock {packager.xyz(POWER)} minecraft:redstone_block")
        before = packager.block_data(world, MACHINE)
        assert "HeldBox:" in before and packager.number(before, "AnimationTicks") > 0, before
        world.call("save")
        world.restart()
        reopened = packager.block_data(world, MACHINE)
        assert "HeldBox:" in reopened, reopened
        assert packager.string(reopened, "SignAddress") == "Warehouse A", reopened
        assert contents(world) == "0:minecraft:iron_ingot=5|1:minecraft:redstone=2", contents(world)
        assert not packager.describe_slots(packager.block_value(world, BARREL, "Items"), "Slot")
        remaining = packager.number(reopened, "AnimationTicks")
        assert 0 < remaining <= packager.number(before, "AnimationTicks"), (before, reopened)
        for _ in range(remaining):
            world.step_to(world.clock() + 1)
        settled = packager.block_data(world, MACHINE)
        assert "HeldBox:" in settled and packager.number(settled, "AnimationTicks") == 0, settled

        # Retrieve the parcel, reject a full target without changing either side,
        # then accept it once two target slots are free.
        name = "@s"
        world.command(f"/item replace entity {name} weapon.mainhand with minecraft:stick")
        world.call("wait", 3)
        click(world)
        multiplayer.until("the Packager parcel to reach the player", lambda: any(
            entry.get("item", "").startswith("create:cardboard_package_")
            for entry in world.call("inventory")["hotbar"]
        ))
        hotbar = world.call("inventory")["hotbar"]
        package_slot = next(
            entry["slot"] for entry in hotbar
            if entry.get("item", "").startswith("create:cardboard_package_")
        )
        world.command(
            f"/item replace entity {name} weapon.mainhand from entity {name} hotbar.{package_slot}"
        )
        multiplayer.until("the Packager parcel to be held", lambda:
            (world.call("inventory")["held"] or {}).get("item", "").startswith("create:cardboard_package_")
        )

        world.commands(
            f"/item replace block {packager.xyz(BARREL)} container.{slot} with minecraft:stone 64"
            for slot in range(27)
        )
        full_before = packager.block_value(world, BARREL, "Items")
        held_before = world.call("inventory")["held"]
        click(world)
        held_after = world.call("inventory")["held"]
        full_after = packager.block_value(world, BARREL, "Items")
        assert held_after == held_before, (held_before, held_after)
        assert packager.describe_slots(full_after, "Slot") == packager.describe_slots(full_before, "Slot")

        world.commands(
            f"/item replace block {packager.xyz(BARREL)} container.{slot} with minecraft:air"
            for slot in (25, 26)
        )
        click(world)
        multiplayer.until("the accepted Packager parcel to leave the player's hand", lambda:
            not (world.call("inventory")["held"] or {}).get("item", "").startswith("create:cardboard_package_")
        )
        unpacked = packager.describe_slots(packager.block_value(world, BARREL, "Items"), "Slot")
        assert "minecraft:iron_ingot=5" in unpacked and "minecraft:redstone=2" in unpacked, unpacked
        print("Packager idle and active state survived reopen; a full Barrel rejected without loss, then accepted the addressed parcel once space was available.")


if __name__ == "__main__":
    main()
