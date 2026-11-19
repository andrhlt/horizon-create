#!/usr/bin/env python3
"""Check the exact Elevator Contact item ID, clone item, and survival drops."""
import argparse
from pathlib import Path

from fixture_world import fixture_world

CONTACT = "create:elevator_contact"
REDSTONE_CONTACT = "create:redstone_contact"
POSITION = (8, 105, -12)


def inventory_count(world, item):
    return world.call("inventory")["counts"].get(item, 0)


def commands(world, *lines):
    for line in lines:
        world.call("command", line)


def nearby_drops(world):
    drops = world.call("entities", 8, "minecraft:item")["entities"]
    return sorted(
        (entry["item"]["item"], entry["item"]["count"])
        for entry in drops if entry.get("item")
    )


def run(args):
    env = {"HORIZON_NO_AUDIO": "1"}
    with fixture_world(args, "ElevatorContactItem", render=True, pack=args.pack, env=env) as world:
        x, y, z = POSITION
        commands(world,
            "/fill 5 103 -15 11 103 -9 minecraft:stone",
            f"/tp @s {x + .5} {y - 1} {z + 2.5}",
            "/gamemode creative",
            f"/setblock {x} {y} {z} {CONTACT}[facing=south,powered=false,calling=false,powering=false]",
        )
        world.call("wait", 3)
        if not args.clone_only:
            commands(world, f"/give @s {CONTACT}")
            world.call("wait", 2)
        if not args.clone_only and inventory_count(world, CONTACT) != 1:
            raise RuntimeError(f"The exact {CONTACT} item could not be given.")

        commands(world, "/clear @s")
        world.call("look-at", x + .5, y + .5, z + .5)
        world.call("mouse", "middle", "click")
        world.call("wait", 3)
        clone = world.call("inventory")["counts"]
        if clone.get(REDSTONE_CONTACT, 0) != 1 or clone.get(CONTACT, 0):
            raise RuntimeError(f"Pick Block returned {clone}; expected one {REDSTONE_CONTACT}.")

        if args.clone_only:
            print("Pick Block returned one redstone_contact.")
            return

        commands(world,
            "/clear @s",
            "/gamemode survival",
            f"/setblock {x} {y} {z} {CONTACT}[facing=south,powered=false,calling=false,powering=false]",
            "/give @s minecraft:iron_pickaxe",
        )
        world.call("wait", 3)
        world.call("select", "minecraft:iron_pickaxe")
        commands(world, "/tick unfreeze")
        world.call("break", *POSITION, "--timeout", 8)
        commands(world, "/tick freeze")
        if world.call("block", *POSITION)["block"] != "minecraft:air":
            raise RuntimeError("The survival player did not break the Elevator Contact.")
        drops = nearby_drops(world)
        if drops != [(REDSTONE_CONTACT, 1)]:
            raise RuntimeError(f"Breaking {CONTACT} dropped {drops}; expected one {REDSTONE_CONTACT}.")

    print("Elevator Contact registered its exact item ID; Pick Block and survival breaking returned one redstone_contact.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--clone-only", action="store_true",
                        help="skip item registration and survival break checks for a clone-only baseline")
    run(parser.parse_args())
