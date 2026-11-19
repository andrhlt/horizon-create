#!/usr/bin/env python3
"""Check the Shopping List's ordinary use and deliberate discard."""

import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

mp = import_module("test-multiplayer")
ITEM = "create:shopping_list"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()

    with fixture_world(args, "ShoppingList", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.commands((
            "/fill 6 169 19 10 169 23 minecraft:stone",
            "/tp @s 8.5 170 21.5",
            "/gamemode survival",
        ))
        for aim in ((8.5, 184, 24.5), (8.5, 169.7, 21.5)):
            world.command(f"/item replace entity @s hotbar.0 with {ITEM}")
            mp.until("held Shopping List", lambda: (world.call("inventory")["held"] or {}).get("item") == ITEM)
            world.call("look-at", *aim)
            world.call("mouse", "right", "click")
            world.call("wait", 3)
            assert world.call("inventory")["counts"].get(ITEM) == 1
            world.call("key", "shift", "down")
            world.call("wait", 3)
            world.call("mouse", "right", "click")
            mp.until("discarded Shopping List", lambda: ITEM not in world.call("inventory")["counts"])
            world.call("key", "shift", "up")
    print("Ordinary use retained the Shopping List. Sneak-use discarded it in air and on a block.")


if __name__ == "__main__":
    main()
