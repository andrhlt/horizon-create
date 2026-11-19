#!/usr/bin/env python3
"""Compare a LAN guest's survival Tree Fertilizer uses with the Java oracle."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
ITEM = "create:tree_fertilizer"
GUEST = "TreeGuest"


def give_and_aim(host, guest, at, target):
    host.commands((f"/tp {GUEST} {at[0]} {at[1]} {at[2]}",
                   f"/item replace entity {GUEST} hotbar.0 with {ITEM} 2"))
    multiplayer.until("the guest to reach the saplings", lambda:
                      guest.call("state")["player"]["position"] == list(at))
    multiplayer.until("the guest to hold two fertilizer", lambda: multiplayer.count(guest, ITEM) == 2)
    guest.call("select", ITEM)
    guest.call("look-at", target[0] + 0.5, target[1] + 0.35, target[2] + 0.5)
    multiplayer.until("the guest to target the sapling", lambda:
                      (guest.call("looking-at").get("block") or {}).get("pos") == list(target))
    guest.call("mouse", "right", "click")


def assert_consumed(host, guest, expected):
    remaining = int(expected["remaining"])
    multiplayer.until("the guest inventory to show one fertilizer", lambda: multiplayer.count(guest, ITEM) == remaining)
    inventory = host.command(f"/data get entity {GUEST} Inventory")
    if f'count: {remaining}' not in inventory or ITEM not in inventory:
        raise RuntimeError(f"Host inventory did not reflect fertilizer consumption: {inventory}")


def run(args, scratch):
    with (ROOT / "fixtures/tree_fertilizer_obstructions-java.csv").open() as source:
        rows = {row["case"]: row for row in csv.DictReader(source)}
    with fixture_world(args, "TreeFertilizerGuest", pack=args.pack, env={"HORIZON_NO_AUDIO": "1"}) as host:
        network = host.call("lan", "open", 0, "commands", "force")
        with multiplayer.joined_client(args, scratch, f"127.0.0.1:{network['port']}", GUEST,
                                       render=True, scenario="multiplayer-tree-fertilizer", pack=args.pack,
                                       env={"HORIZON_NO_AUDIO": "1"}) as guest:
            multiplayer.until("the independent guest to join", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]))
            host.command(f"/gamemode survival {GUEST}")
            host.commands((
                "/fill 6 169 20 14 169 28 minecraft:dirt",
                "/fill 6 170 20 14 185 28 minecraft:air",
                "/setblock 10 170 22 minecraft:oak_sapling[stage=0]",
                "/setblock 10 171 22 minecraft:stone",
                "/setblock 10 172 22 minecraft:bedrock",
            ))
            give_and_aim(host, guest, (10.5, 170.0, 25.5), (10, 170, 22))
            multiplayer.until("the host to grow the oak", lambda:
                              host.call("block", 10, 170, 22)["block"] == "minecraft:oak_log")
            row = rows["combined"]
            trunk = host.call("block", 10, 171, 22)["block"] == "minecraft:oak_log"
            cap = host.call("block", 10, 172, 22)["block"] == "minecraft:bedrock"
            if trunk != (row["trunk_y1_oak_log"] == "true") or cap != (row["bedrock_y2_preserved"] == "true"):
                raise RuntimeError(f"Host oak obstruction results differ from Java: trunk={trunk}, bedrock={cap}")
            assert_consumed(host, guest, row)
            bases = [(x, 170, z) for x in (9, 10) for z in (23, 24)]
            host.commands((
                "/fill 5 169 18 15 169 28 minecraft:dirt",
                "/fill 5 170 18 15 199 28 minecraft:air",
                *(f"/setblock {x} {y} {z} minecraft:spruce_sapling[stage=0]" for x, y, z in bases),
            ))
            give_and_aim(host, guest, (10.5, 170.0, 27.5), (10, 170, 24))
            row = rows["spruce_2x2"]
            multiplayer.until("the host to grow four spruce logs", lambda:
                              sum(host.call("block", *at)["block"] == "minecraft:spruce_log" for at in bases) == int(row["spruce_base_logs"]))
            soil = host.call("blocks", 5, 169, 18, 15, 169, 28)["blocks"]
            podzol = sum(state.startswith("minecraft:podzol") for *_, state in soil)
            if podzol != int(row["podzol_count"]):
                raise RuntimeError(f"Host soil differs from Java: {soil}")
            assert_consumed(host, guest, row)
    print("A survival LAN guest grew the obstructed oak and 2x2 spruce; host blocks and fertilizer consumption match Java.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    with TemporaryDirectory(prefix="hc-tree-guest-") as scratch:
        run(parser.parse_args(), Path(scratch))
