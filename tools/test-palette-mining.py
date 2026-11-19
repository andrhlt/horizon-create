#!/usr/bin/env python3
"""Compare real mining drops with the pinned Java metal and stone palette tables."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
GUEST = "PaletteGuest"
POS = (9, 171, 21)
FEET = (9.5, 171, 23.5)


def exercise(host, actor, player, rows):
    host.commands((
        f"/tp {player} {' '.join(map(str, FEET))}",
        f"/gamemode survival {player}",
        f"/effect give {player} minecraft:haste 240 8 true",
    ))
    multiplayer.until("the miner at the fixture", lambda:
                      actor.call("state")["player"]["position"] == list(FEET))
    for row in rows:
        block = row["block"]
        slab = row["slab_type"]
        state = f"{block}[type={slab},waterlogged=false]" if slab != "_" else block
        tool = row["tool"]
        host.commands((
            f"/clear {player}",
            "/kill @e[type=minecraft:item,distance=..16]",
            f"/setblock {' '.join(map(str, POS))} {state}",
        ))
        if tool != "minecraft:air":
            host.command(f"/item replace entity {player} hotbar.0 with {tool}")
            multiplayer.until(f"the {tool} in the miner's inventory",
                              lambda: multiplayer.count(actor, tool) == 1)
            actor.call("select", tool)
        else:
            multiplayer.until("the empty hotbar", lambda: not actor.call("inventory")["counts"])
        multiplayer.until(f"{state} to reach the miner", lambda:
                          actor.call("block", *POS)["block"] == block)
        observed = actor.call("break", *POS, "--timeout", 20)
        quantity = int(row["drop"])
        expected = {block: quantity} if quantity else {}
        before = observed["block_before"]
        matching_state = before == state if slab != "_" else before.split("[", 1)[0] == block
        if not matching_state or observed["block"] != "minecraft:air":
            raise RuntimeError(f"{state} was not mined by {tool}: {observed}")
        if observed["drops"] != expected:
            raise RuntimeError(f"Mining {state} with {tool}: Java {expected}, Horizon {observed['drops']}")
        multiplayer.until(f"{state} removed on the host", lambda:
                          host.call("block", *POS)["block"] == "minecraft:air")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/palette-mining-java.csv").open() as reference:
        rows = list(csv.DictReader(reference))
    with fixture_world(args, "Palette Mining", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 6 170 18 13 170 25 minecraft:stone",
            "/tp @s 9.5 171 25.5",
            "/tick unfreeze",
        ))
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-pmine-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="palette-mining", pack=args.pack,
            ) as guest:
                multiplayer.until("the miner to join", lambda: any(
                    entry["name"] == GUEST and entry["placed"]
                    for entry in host.call("lan", "status")["guests"]
                ))
                exercise(host, guest, GUEST, rows)
        else:
            exercise(host, host, "@s", rows)
    print(f"All {len(rows)} original Java metal and palette drop cases matched.")


if __name__ == "__main__":
    main()
