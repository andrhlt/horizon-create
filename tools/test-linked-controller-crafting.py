#!/usr/bin/env python3
"""Craft the pinned Java Linked Controller recipe in survival."""

import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

machine = import_module("test-machine-crafting")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    with fixture_world(args, "Linked-controller-crafting", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as control:
        control.commands((
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))
        machine.replay(control, {
            "recipe": "crafting/appliances/linked_controller", "width": "3",
            "slots": "minecraft:oak_button,minecraft:oak_button,minecraft:oak_button,_,create:redstone_link,_,minecraft:oak_button,minecraft:oak_button,minecraft:oak_button",
            "output": "create:linked_controller", "count": "1", "remainder": "",
        })
    print("Linked Controller crafted from six wooden buttons and a Redstone Link in survival.")


if __name__ == "__main__":
    main()
