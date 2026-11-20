#!/usr/bin/env python3
"""Check guest Zinc mining, pickup and inventory retention after a host world reopen."""

import argparse
from importlib import import_module
from pathlib import Path
from shutil import rmtree
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")
GUEST = "ZincGuest"
ORE = (9, 171, 21)
RAW_ZINC = "create:raw_zinc"


def guest_is_connected(host):
    return any(player["name"] == GUEST and player["placed"]
               for player in host.call("lan", "status")["guests"])


def saved_inventory(host):
    return host.command(f"/data get entity {GUEST} Inventory")


def run(args):
    with fixture_world(args, "Zinc-mining-LAN", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 6 170 18 13 170 25 minecraft:stone",
            f"/setblock {' '.join(map(str, ORE))} create:zinc_ore",
            "/tick unfreeze",
        ))
        with TemporaryDirectory(prefix="hc-zinc-lan-") as scratch:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            address = f"127.0.0.1:{port}"
            with multiplayer.joined_client(
                args, Path(scratch), address, GUEST, render=True,
                scenario="zinc-mining-lan", pack=args.pack,
            ) as guest:
                multiplayer.until("the Zinc miner to join", lambda: guest_is_connected(host))
                host.commands((
                    f"/gamemode survival {GUEST}",
                    f"/tp {GUEST} 9.5 171 23.5",
                    f"/item replace entity {GUEST} hotbar.0 with minecraft:iron_pickaxe 1",
                ))
                multiplayer.until("the guest's survival pickaxe", lambda:
                                  multiplayer.count(guest, "minecraft:iron_pickaxe") == 1)
                multiplayer.until("the Zinc ore on the guest client", lambda:
                                  guest.call("block", *ORE)["block"] == "create:zinc_ore")
                result = guest.call("break", *ORE, "--timeout", 30)
                if result["block_before"].split("[", 1)[0] != "create:zinc_ore":
                    raise RuntimeError(f"Guest did not mine Zinc Ore: {result}")
                if result["block"] != "minecraft:air" or result["drops"] != {RAW_ZINC: 1}:
                    raise RuntimeError(f"Unexpected guest Zinc mining result: {result}")
                multiplayer.until("the host to see the mined block", lambda:
                                  host.call("block", *ORE)["block"] == "minecraft:air")
                host.command(f"/tp {GUEST} 9.5 171 22.0")
                multiplayer.until("the guest beside the Zinc drop", lambda:
                                  guest.call("state")["player"]["position"] == [9.5, 171.0, 22.0])
                guest.call("wait", 5)
                multiplayer.until("host and guest inventories to agree", lambda:
                                  multiplayer.count(guest, RAW_ZINC) == 1
                                  and RAW_ZINC in saved_inventory(host))
                inventory = saved_inventory(host)
                if "count: 1" not in inventory:
                    raise RuntimeError(f"Host saved an unexpected Zinc inventory: {inventory}")

            multiplayer.until("the guest to disconnect", lambda: not guest_is_connected(host))
            host.restart()
            if host.call("block", *ORE)["block"] != "minecraft:air":
                raise RuntimeError("The mined ore reappeared when the host reopened the world.")
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            rmtree(Path(scratch) / GUEST / "horizon-mods")
            with multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="zinc-mining-rejoin", pack=args.pack,
            ) as guest:
                multiplayer.until("the guest to rejoin the reopened world", lambda: guest_is_connected(host))
                multiplayer.until("the raw Zinc to return to the guest", lambda:
                                  multiplayer.count(guest, RAW_ZINC) == 1)
                if RAW_ZINC not in saved_inventory(host) or "count: 1" not in saved_inventory(host):
                    raise RuntimeError(f"The reopened host lost the guest's Zinc: {saved_inventory(host)}")
    print("A survival LAN guest mined and picked up one Raw Zinc; the host agreed and retained the inventory after world reopen and guest rejoin.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
