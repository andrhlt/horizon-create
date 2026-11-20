#!/usr/bin/env python3
"""Pour bottles and collect Item Drain cargo from independent clients."""

import argparse
from importlib import import_module
from pathlib import Path
import re
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
            # Both real player interaction routes must clear authoritative cargo
            # and deliver it once to the acting player's replicated inventory.
            for player, name, held in ((host, "@s", None), (guest, GUEST, "minecraft:stick")):
                host.commands((
                    "/setblock 5 97 -9 minecraft:smooth_stone",
                    "/item replace block 4 97 -9 container.0 with minecraft:iron_ingot 3",
                    "/data merge block 4 97 -9 {HeldItem:{Pos:1.0f,InDirection:5}}",
                    f"/item replace entity {name} hotbar.8 with minecraft:air",
                    f"/item replace entity {name} hotbar.1 with minecraft:stick",
                ))
                host.step_to(host.clock() + 1)
                cargo = drain.values(host.command("/data get block 4 97 -9"))[1:3]
                if cargo != ("minecraft:iron_ingot", 3):
                    raise RuntimeError(f"Collection fixture did not seed cargo: {cargo}")
                multiplayer.until("the collection stick to replicate", lambda: multiplayer.count(player, "minecraft:stick") == 1)
                before = multiplayer.count(player, "minecraft:iron_ingot")
                player.call("select", held or 9)
                player.call("interact", *POSITION, "up")
                multiplayer.until("the player's collected cargo", lambda: multiplayer.count(player, "minecraft:iron_ingot") == before + 3)
                multiplayer.until("the authoritative drain cargo to clear", lambda: drain.values(host.command("/data get block 4 97 -9"))[1:3] == ("minecraft:air", 0))
                player.call("interact", *POSITION, "up")
                # Let the second network interaction arrive even though the
                # simulation is frozen, then inspect both server and actor.
                player.call("wait", 10)
                authoritative = host.command(f"/data get entity {name} Inventory")
                server_total = sum(int(re.search(r'count: (\d+)', entry)[1])
                                   for entry in re.findall(r'\{[^{}]*\}', authoritative)
                                   if 'id: "minecraft:iron_ingot"' in entry)
                if server_total != before + 3 or multiplayer.count(player, "minecraft:iron_ingot") != before + 3:
                    raise RuntimeError(f"Repeated collection changed cargo: {authoritative}; {player.call('inventory')}")
            if drain.values(host.command("/data get block 4 97 -9"))[-2:] != ("create:honey", 500):
                raise RuntimeError("Cargo collection changed the shared 500 mB honey fill")
    print("Host and guest each poured honey and received an empty bottle; host empty-hand and guest stick collection conserved cargo and shared fluid.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    with TemporaryDirectory(prefix="hc-drain-lan-") as scratch:
        run(parser.parse_args(), Path(scratch))


if __name__ == "__main__":
    main()
