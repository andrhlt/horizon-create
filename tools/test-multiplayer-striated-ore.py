#!/usr/bin/env python3
"""Check guest mining and persistence for Java-defined Striated Ore drops."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from shutil import rmtree
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")
GUEST = "StriatedGuest"
BASE = (8, 171, 21)


def read_reference():
    with (Path(__file__).resolve().parents[1] / "fixtures/striated-ore-drops-java.csv").open(newline="") as source:
        return list(csv.DictReader(source))


def guest_connected(host):
    return any(player["name"] == GUEST and player["placed"]
               for player in host.call("lan", "status")["guests"])


def run(args):
    rows = read_reference()
    positions = [(BASE[0] + index % 4, BASE[1], BASE[2] + index // 4) for index in range(len(rows))]
    with fixture_world(args, "Striated-ore-LAN", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 6 170 18 15 170 25 minecraft:stone",
            "/gamemode survival",
            "/tick unfreeze",
        ))
        with TemporaryDirectory(prefix="hc-striated-lan-") as scratch:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            with multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="striated-ore-mining-lan", pack=args.pack,
            ) as guest:
                multiplayer.until("the Striated Ore miner to join", lambda: guest_connected(host))
                host.commands((
                    f"/gamemode survival {GUEST}",
                    f"/item replace entity {GUEST} hotbar.0 with minecraft:iron_pickaxe 1",
                ))
                for row, at in zip(rows, positions, strict=True):
                    x, y, z = at
                    block = row["block"]
                    host.command(f"/setblock {x} {y} {z} {block}")
                    host.command(f"/tp {GUEST} {x + 0.5} {y} {z + 2.5}")
                    multiplayer.until(f"guest to receive {block}", lambda at=at, block=block:
                                      guest.call("block", *at)["block"] == block)
                    result = guest.call("break", *at, "--timeout", 30)
                    expected = {row["drop"]: int(row["count"])}
                    if result["block_before"].split("[", 1)[0] != block:
                        raise RuntimeError(f"Guest mined an unexpected block: {result}")
                    if result["block"] != "minecraft:air" or result["drops"] != expected:
                        raise RuntimeError(f"{block}: expected {expected}, got {result}")
                    multiplayer.until(f"host to observe mined {block}", lambda at=at:
                                      host.call("block", *at)["block"] == "minecraft:air")
                    host.command(f"/tp {GUEST} {x + 0.5} {y} {z + 0.5}")
                    multiplayer.until(f"guest to pick up {row['drop']}", lambda drop=row["drop"]:
                                      multiplayer.count(guest, drop) == 1)
                inventory_before = host.command(f"/data get entity {GUEST} Inventory")
                for row in rows:
                    if row["drop"] not in inventory_before:
                        raise RuntimeError(f"Host inventory omitted {row['drop']}: {inventory_before}")

            multiplayer.until("guest to disconnect", lambda: not guest_connected(host))
            host.restart()
            for at in positions:
                if host.call("block", *at)["block"] != "minecraft:air":
                    raise RuntimeError(f"Mined Striated Ore reappeared after host reopen at {at}.")
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            rmtree(Path(scratch) / GUEST / "horizon-mods")
            with multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="striated-ore-mining-rejoin", pack=args.pack,
            ) as guest:
                multiplayer.until("guest to rejoin the reopened host", lambda: guest_connected(host))
                multiplayer.until("all seven drops to return to the guest", lambda:
                                  all(multiplayer.count(guest, row["drop"]) == 1 for row in rows))
                inventory_after = host.command(f"/data get entity {GUEST} Inventory")
                if inventory_after != inventory_before:
                    raise RuntimeError(f"Guest inventory changed across host reopen: {inventory_before} -> {inventory_after}")
    print(f"A LAN guest mined all {len(rows)} Striated stone variants; drops matched Java and the mined state and inventory survived host reopen and guest rejoin.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
