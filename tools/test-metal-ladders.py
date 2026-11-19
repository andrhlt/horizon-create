#!/usr/bin/env python3
"""Compare Java Metal Ladder crafting, placement assist and hanging support."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

bars = import_module("test-metal-bars")
multiplayer = import_module("test-multiplayer")
GUEST = "MetalLadderGuest"


def reference(kind):
    with (ROOT / f"fixtures/metal-ladder-{kind}-java.csv").open(newline="") as source:
        return list(csv.DictReader(source))


def compare_state(host, actor, rows, x, y, z, block):
    for row in rows:
        pos = (x, y + int(row["offset"]), z)
        actual = host.call("block", *pos)
        props = dict(re.findall(r"(\w+)=(\w+)", actual["state"]))
        wet = props.get("waterlogged") == "true" or actual["block"] == "minecraft:water"
        actual_row = actual["block"], props.get("facing", "_"), wet
        expected = row["block"], row["facing"], row["fluid_source"] == "true"
        if actual_row != expected:
            raise RuntimeError(f"Java {row} at {pos}. Horizon {actual_row}.")
        multiplayer.until(f"{row['material']} ladder at {pos} to synchronize",
                          lambda: actor.call("block", *pos)["state"] == actual["state"])
    held = int(rows[0]["held"])
    multiplayer.until(f"the holder to have {held} {block}", lambda:
                      actor.call("inventory")["counts"].get(block, 0) == held)


def exercise(host, actor, player, recipes, reference_states):
    for index, recipe in enumerate(recipes):
        block = recipe["block"]
        x, y, z = 8 + 4 * index, 173, 20
        material = block.split(":", 1)[1].removesuffix("_ladder")
        states = [row for row in reference_states if row["material"] == material]
        host.commands((
            f"/clear {player}",
            f"/item replace entity {player} hotbar.0 with {block} 5",
            f"/setblock {x} {y} {z+1} minecraft:stone",
        ))
        multiplayer.until(f"five {block} to arrive", lambda:
                          actor.call("inventory")["counts"].get(block) == 5)
        actor.call("select", block)
        for tick in range(1, 8):
            if tick in (1, 4):
                stance = (f"/tp {player} {x+0.5} {y-1} {z-1.5} 0 " +
                          ("-40" if tick == 4 else "40"))
                host.command(stance)
                actor.call("wait", 5)
            if tick == 1:
                actor.call("interact", x, y, z + 1, "north")
            if tick in (2, 3, 4):
                if tick == 4:
                    host.command(f"/setblock {x} {y+1} {z+1} minecraft:stone")
                actor.call("interact", x, y, z, "north")
            if tick == 5:
                host.command(f"/setblock {x} {y} {z+1} minecraft:air")
            if tick == 6:
                host.command(f"/item replace entity {player} hotbar.8 with minecraft:water_bucket")
                multiplayer.until("a water bucket to arrive", lambda:
                                  actor.call("inventory")["counts"].get("minecraft:water_bucket") == 1)
                host.command(f"/fill {x} {y-2} {z-2} {x} {y-2} {z-1} minecraft:air")
                host.command(f"/tp {player} {x+0.5} {y-2} {z-1.5} 0 35")
                actor.call("wait", 5)
                actor.call("select", "minecraft:water_bucket")
                actor.call("interact", x, y - 2, z, "north")
            if tick == 7:
                host.command(f"/setblock {x} {y+1} {z+1} minecraft:air")
            host.step_to(host.clock() + 1)
            compare_state(host, actor, [row for row in states if int(row["tick"]) == tick], x, y, z, block)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    recipes, states = reference("recipe"), reference("state")
    with fixture_world(args, "Metal-ladders", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 5 170 14 23 170 28 minecraft:stone",
            "/fill 5 171 14 23 171 19 minecraft:stone",
            "/setblock 11 171 24 minecraft:stonecutter",
            "/tp @s 11.5 171 26.5",
            "/gamemode survival",
        ))
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-metal-ladder-lan-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="metal-ladders", pack=args.pack,
            ) as guest:
                multiplayer.until("the ladder guest to join", lambda: any(
                    p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]
                ))
                host.command(f"/gamemode survival {GUEST}")
                exercise(host, guest, GUEST, recipes, states)
        else:
            for slot, recipe in enumerate(recipes):
                bars.cut(host, recipe, slot)
            exercise(host, host, "@s", recipes, states)
    print(f"All {len(states)} Metal Ladder placement, hanging support and water states match Java.")


if __name__ == "__main__":
    main()
