#!/usr/bin/env python3
"""Compare Java Create metal block recipes, survival placement, and Wrench pickup."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

bars = import_module("test-metal-bars")
crafting = import_module("test-machine-crafting")
multiplayer = import_module("test-multiplayer")
wrench = import_module("test-wrench")
GUEST = "MetalBlockGuest"


def reference(name):
    with (ROOT / f"fixtures/metal-construction-{name}-java.csv").open() as source:
        return list(csv.DictReader(source))


def place_and_pick_up(host, actor, player, rows):
    for index, row in enumerate(rows):
        x, y, z = 8 + index * 3, 171, 21
        block = row["block"]
        host.commands((
            f"/clear {player}",
            f"/item replace entity {player} hotbar.0 with {block}",
            f"/item replace entity {player} hotbar.1 with create:wrench",
            f"/tp {player} {x+0.5} {y} {z+2.5}",
        ))
        multiplayer.until(f"{block} and its player to arrive", lambda:
                          actor.call("inventory")["counts"].get(block) == 1
                          and actor.call("state")["player"]["position"] == [x+0.5, y, z+2.5])
        actor.call("select", block)
        actor.call("interact", x, y-1, z, "up")
        for client in (host,) if actor is host else (host, actor):
            multiplayer.until(f"{block} to be placed", lambda: client.call("block", x, y, z)["block"] == block)
        multiplayer.until(f"{block} to be consumed",
                          lambda: actor.call("inventory")["counts"].get(block, 0) == 0)
        actor.call("select", "create:wrench")
        wrench.sneak_click(actor, (x+0.5, y+0.5, z+0.5))
        host.step_to(host.clock() + 1)
        for client in (host,) if actor is host else (host, actor):
            multiplayer.until(f"the Wrench outcome for {block}",
                              lambda: client.call("block", x, y, z)["block"] == row["after"])
        multiplayer.until(f"the original pickup count for {block}",
                          lambda: actor.call("inventory")["counts"].get(block, 0) == int(row["picked_up"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    rows = reference("blocks")
    with fixture_world(args, "Metal structure blocks", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 5 170 19 19 170 29 minecraft:stone",
            "/setblock 11 171 24 minecraft:stonecutter",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-metal-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="construction-metals", pack=args.pack,
            ) as guest:
                multiplayer.until("the metal block guest to join", lambda: any(
                    p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]
                ))
                host.command(f"/gamemode survival {GUEST}")
                place_and_pick_up(host, guest, GUEST, rows)
        else:
            # The crafting replay uses a table flush with its own survival platform.
            host.commands((
                "/fill 9 170 25 16 170 28 minecraft:air",
                "/fill 9 169 25 16 169 28 minecraft:stone",
                "/tp @s 12.5 170 26.5",
            ))
            for recipe in reference("crafting"):
                crafting.replay(host, recipe)
            host.command("/clear @s")
            host.command("/setblock 11 170 26 minecraft:stone")
            host.command("/tp @s 11.5 171 26.5")
            for slot, recipe in enumerate(reference("stonecutting")):
                bars.cut(host, recipe, slot)
            place_and_pick_up(host, host, "@s", rows)
    print(f"Survival placement and Wrench outcomes match all {len(rows)} original metal blocks.")


if __name__ == "__main__":
    main()
