#!/usr/bin/env python3
"""Pour two bottles into one Item Drain from independent Horizon clients."""

import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")
drain = import_module("test-item-drain")
GUEST = "DrainGuest"
POSITION = (4, 97, -9)
HONEY = "minecraft:honey_bottle"
BOTTLE = "minecraft:glass_bottle"


def run(args, scratch):
    with fixture_world(args, "Item-drain-LAN", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 3 96 -12 9 96 -6 minecraft:smooth_stone",
            "/setblock 4 97 -9 create:item_drain",
            "/tp @s 4.5 97 -6.5",
            "/gamemode survival",
            f"/item replace entity @s hotbar.0 with {HONEY} 3",
        ))
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with multiplayer.joined_client(
            args, scratch, address, GUEST, render=True,
            scenario="item-drain-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the lab", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} 5.5 97 -10.5",
                f"/item replace entity {GUEST} hotbar.0 with {HONEY} 3",
            ))
            multiplayer.until("the guest setup", lambda: (
                multiplayer.count(guest, HONEY) == 3
                and guest.call("state")["player"]["position"] == [5.5, 97.0, -10.5]
            ))
            for amount, player in ((250, host), (500, guest)):
                player.call("select", HONEY)
                player.call("interact", *POSITION, "up")
                multiplayer.until(f"the drain to contain {amount} mB", lambda: (
                    drain.values(host.command("/data get block 4 97 -9"))[-2:] == ("create:honey", amount)
                ))
                multiplayer.until("the player's empty bottle", lambda: (
                    multiplayer.count(player, HONEY) == 2 and multiplayer.count(player, BOTTLE) == 1
                ))
    print("Host and guest each poured a honey bottle, received an empty bottle and filled the drain to 500 mB.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    with TemporaryDirectory(prefix="hc-drain-lan-") as scratch:
        run(parser.parse_args(), Path(scratch))


if __name__ == "__main__":
    main()
