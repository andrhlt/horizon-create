#!/usr/bin/env python3
"""Check Java's full-Netherite-diving-set fire immunity for a survival player."""
import argparse
from pathlib import Path

from fixture_world import fixture_world


def run(args):
    with fixture_world(args, "NetheriteDivingImmunity", render=False, pack=args.pack) as world:
        world.command("/gamemode survival")
        world.commands((
            "/fill 5 169 19 17 169 28 minecraft:stone",
            "/tp @s 9.5 170 25.5 180 0",
            "/item replace entity @s armor.head with create:netherite_diving_helmet",
            "/item replace entity @s armor.legs with minecraft:netherite_leggings",
            "/item replace entity @s armor.feet with create:netherite_diving_boots",
        ))
        world.command("/setblock 9 170 24 create:netherite_backtank[facing=south,waterlogged=false]")
        world.command("/data merge block 9 170 24 {Air:900}")
        world.call("interact", 9, 170, 24, "south")
        world.call("wait", 2)
        equipment = world.command("/data get entity @s equipment")
        required = (
            'id: "create:netherite_diving_helmet"',
            'id: "create:netherite_backtank"',
            '"create:banktank_air": 900',
            'id: "minecraft:netherite_leggings"',
            'id: "create:netherite_diving_boots"',
        )
        if not all(value in equipment for value in required):
            raise RuntimeError(f"The full charged Netherite diving set was not equipped: {equipment}")
        world.command("/damage @s 4 minecraft:lava")
        world.call("wait", 2)
        immune_health = world.call("state")["player"]["health"]
        if immune_health != 20:
            raise RuntimeError(f"A fully equipped charged Netherite diving suit took lava damage: {immune_health}")

        world.command("/item replace entity @s armor.head with minecraft:air")
        world.call("wait", 2)
        world.command("/damage @s 4 minecraft:lava")
        world.call("wait", 2)
        control_health = world.call("state")["player"]["health"]
        if control_health >= immune_health:
            raise RuntimeError(f"Removing the diving helmet did not restore normal lava damage: {control_health}")
        print(f"Full Netherite suit blocked lava damage at {immune_health} health; helmet-off control fell to {control_health}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=lambda path: Path(path).resolve())
    run(parser.parse_args())
