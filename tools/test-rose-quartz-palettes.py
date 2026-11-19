#!/usr/bin/env python3
"""Replay original Create Rose Quartz placement and Stonecutter outputs."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

stonecutter = import_module("test-metal-bars")
multiplayer = import_module("test-multiplayer")
DIRECTIONS = {"east": (1, 0, 0), "up": (0, 1, 0), "south": (0, 0, 1)}
GUEST = "QuartzGuest"


def reference(folder, name):
    with (folder / f"rose-quartz-{name}-java.csv").open() as source:
        return list(csv.DictReader(source))


def place(host, actor, player, rows):
    for index, row in enumerate(rows):
        block = row["block"]
        pos = (7 + index * 2, 171, 20)
        offset = DIRECTIONS[row["face"]]
        support = tuple(cell - step for cell, step in zip(pos, offset, strict=True))
        host.commands((
            f"/setblock {' '.join(map(str, support))} minecraft:stone",
            f"/tp {player} {pos[0] + .5} 171 22.5",
            f"/item replace entity {player} hotbar.0 with {block}",
        ))
        multiplayer.until(f"{block} to arrive", lambda: actor.call("inventory")["counts"].get(block) == 1)
        actor.call("select", block)
        actor.call("interact", *support, row["face"])
        multiplayer.until(f"{block} to be placed", lambda: host.call("block", *pos)["block"] == block)
        state = host.call("block", *pos)["state"]
        if row["axis"] != "_" and f"axis={row['axis']}" not in state:
            raise RuntimeError(f"Create Java placed {block} at axis {row['axis']}, Horizon {state}.")
        multiplayer.until(f"{block} state to reach the client", lambda: actor.call("block", *pos)["state"] == state)
        multiplayer.until(f"the placed {block} to leave the player's inventory",
                          lambda: block not in actor.call("inventory")["counts"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    states, cuts = (reference(ROOT / "fixtures", name) for name in ("states", "cutting"))
    with fixture_world(args, "Rose Quartz palettes", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 5 170 16 24 170 27 minecraft:stone",
            "/setblock 11 171 24 minecraft:stonecutter",
            "/tp @s 11.5 171 26.5",
            "/gamemode survival",
        ))
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-quartz-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="rose-quartz-palettes", pack=args.pack,
            ) as guest:
                multiplayer.until("the guest to join", lambda: any(
                    p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]
                ))
                host.command(f"/gamemode survival {GUEST}")
                place(host, guest, GUEST, states)
        else:
            for slot, entry in enumerate(cuts):
                stonecutter.cut(host, entry, slot)
            host.command("/clear @s")
            place(host, host, "@s", states)
    details = "" if args.lan else f" and {len(cuts)} Stonecutter outputs"
    print(f"Matched {len(states)} original Java Rose Quartz placement cases{details}.")


if __name__ == "__main__":
    main()
