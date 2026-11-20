#!/usr/bin/env python3
"""Craft an Andesite Alloy as a LAN guest and retain it across host reopen."""

import argparse
from importlib import import_module
from pathlib import Path
from shutil import rmtree
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")
crafting = import_module("test-survival-crafting")
GUEST = "PartsGuest"
OUTPUT = "create:andesite_alloy"


def connected(host):
    return any(player["name"] == GUEST and player["placed"]
               for player in host.call("lan", "status")["guests"])


def saved_inventory(host):
    return host.command(f"/data get entity {GUEST} Inventory")


def assert_saved_craft(host):
    inventory = saved_inventory(host)
    if OUTPUT not in inventory or "count: 1" not in inventory:
        raise RuntimeError(f"Host did not retain exactly one Andesite Alloy for the guest: {inventory}")
    if "minecraft:andesite" in inventory or "minecraft:iron_nugget" in inventory:
        raise RuntimeError(f"Host retained crafting ingredients after the craft: {inventory}")


def run(args):
    with fixture_world(args, "Common-parts-crafting-LAN", render=True, pack=args.pack) as host:
        host.command("/tick unfreeze")
        host.command("/gamemode survival")
        with TemporaryDirectory(prefix="hc-common-parts-lan-") as scratch:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            address = f"127.0.0.1:{port}"
            with multiplayer.joined_client(
                args, Path(scratch), address, GUEST, render=True,
                scenario="common-parts-crafting-lan", pack=args.pack,
            ) as guest:
                multiplayer.until("the crafting guest to join", lambda: connected(host))
                host.command(f"/gamemode survival {GUEST}")
                host.commands((
                    f"/give {GUEST} minecraft:andesite 2",
                    f"/give {GUEST} minecraft:iron_nugget 2",
                ))
                multiplayer.until("the guest's crafting ingredients", lambda:
                                  multiplayer.count(guest, "minecraft:andesite") == 2
                                  and multiplayer.count(guest, "minecraft:iron_nugget") == 2)
                guest.call("open-inventory")
                crafting.distribute(guest, 0, (101, 102))
                crafting.distribute(guest, 1, (100, 103))
                crafting.craft(guest, OUTPUT, 1)
                guest.call("close")
                counts = guest.call("inventory")["counts"]
                if counts.get(OUTPUT) != 1 or counts.get("minecraft:andesite", 0) or counts.get("minecraft:iron_nugget", 0):
                    raise RuntimeError(f"Guest crafting left unexpected inventory: {counts}")
                multiplayer.until("the host to retain the guest's crafted alloy", lambda:
                                  OUTPUT in saved_inventory(host))
                assert_saved_craft(host)

            multiplayer.until("the crafting guest to disconnect", lambda: not connected(host))
            host.restart()
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            rmtree(Path(scratch) / GUEST / "horizon-mods")
            with multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="common-parts-crafting-rejoin", pack=args.pack,
            ) as guest:
                multiplayer.until("the crafting guest to rejoin after world reopen", lambda: connected(host))
                multiplayer.until("the saved alloy to return to the guest inventory", lambda:
                                  multiplayer.count(guest, OUTPUT) == 1)
                counts = guest.call("inventory")["counts"]
                if counts.get(OUTPUT) != 1 or counts.get("minecraft:andesite", 0) or counts.get("minecraft:iron_nugget", 0):
                    raise RuntimeError(f"Reopened guest inventory changed: {counts}")
                assert_saved_craft(host)
    print("A LAN guest crafted one Andesite Alloy; consumed inputs and the resulting inventory survived host save/reopen and guest rejoin.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())


if __name__ == "__main__":
    main()
