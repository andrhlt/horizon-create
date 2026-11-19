#!/usr/bin/env python3
"""Replay original Create Metal Ladder Wrench and climbing traces in survival."""

import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

ladders = import_module("test-metal-ladders")
multiplayer = import_module("test-multiplayer")
wrench = import_module("test-wrench")
GUEST = "LadderGuest"


def exercise(host, actor, player, rows):
    for index, material in enumerate(dict.fromkeys(row["material"] for row in rows)):
        x, y, z = 8 + 5 * index, 173, 20
        ladder = f"create:{material}_ladder"
        host.commands((
            f"/clear {player}",
            f"/item replace entity {player} hotbar.0 with create:wrench",
            f"/setblock {x} {y} {z+1} minecraft:stone",
            f"/setblock {x} {y} {z} {ladder}[facing=north]",
        ))
        multiplayer.until("the Wrench to arrive", lambda:
                          actor.call("inventory")["counts"].get("create:wrench") == 1)
        actor.call("select", "create:wrench")
        for row in (row for row in rows if row["material"] == material):
            tick = int(row["tick"])
            if tick == 1:
                host.command(f"/tp {player} {x+0.5} {y-1} {z-1.5}")
                actor.call("wait", 5)
                actor.call("interact", x, y, z, "north")
            elif tick in (2, 3):
                if tick == 2:
                    host.command(f"/tp {player} {x+0.5} {y+1} {z+0.9}")
                    actor.call("wait", 5)
                else:
                    host.command(f"/setblock {x-1} {y} {z} minecraft:stone")
                actor.call("look-at", x + 0.5, y + 1, z + 0.9)
                actor.call("mouse", "right", "click")
                actor.call("wait", 3)
            elif tick == 4:
                host.command(f"/setblock {x} {y} {z+1} minecraft:air")
            elif tick == 5:
                host.command(f"/tp {player} {x+2.5} {y-1} {z+0.5}")
                actor.call("wait", 5)
                wrench.sneak_click(actor, (x + 0.15, y + 0.5, z + 0.5))
            host.step_to(host.clock() + 1)
            state = host.call("block", x, y, z)["state"]
            block, properties = wrench.state(state)
            actual = block, properties.get("facing", "_")
            expected = row["block"], row["facing"]
            if actual != expected:
                raise RuntimeError(f"{material} tick {tick}: Java {expected}, Horizon {actual}")
            multiplayer.until(f"{material} tick {tick} state to synchronize", lambda:
                              actor.call("block", x, y, z)["state"] == state)
            count = int(row["inventory"])
            multiplayer.until(f"{material} tick {tick} inventory to match", lambda:
                              actor.call("inventory")["counts"].get(ladder, 0) == count)


def climb(host, actor, player, rows):
    for index, material in enumerate(dict.fromkeys(row["material"] for row in rows)):
        x, y, z = 8 + 5 * index, 173, 20
        ladder = f"create:{material}_ladder"
        host.commands((
            f"/setblock {x} {y-1} {z} minecraft:stone",
            f"/fill {x} {y} {z+1} {x} {y+4} {z+1} minecraft:stone",
            f"/fill {x} {y} {z} {x} {y+4} {z} {ladder}[facing=north]",
            f"/tp {player} {x+0.5} {y} {z+0.5} 0 0",
        ))
        multiplayer.until("the player and ladder to synchronize", lambda:
                          actor.call("state")["player"]["position"] == [x+0.5, y, z+0.5]
                          and actor.call("block", x, y, z)["block"] == ladder)
        actor.call("wait", 5)
        reference = [row for row in rows if row["material"] == material]
        replies = actor.call("script", script="state\nkey w down\n"
                             + "wait 1\nstate\n" * (len(reference) - 1) + "key w up\n")
        samples = [reply["player"] for reply in replies if "player" in reply]
        for row, sample in zip(reference, samples, strict=True):
            tick = int(row["tick"])
            dy = sample["position"][1] - y
            vy = sample["velocity"][1]
            within_column = sample["block_pos"][::2] == [x, z] and y <= sample["block_pos"][1] < y+5
            if (abs(dy - float(row["dy"])) > 1e-7 or
                    abs(vy - float(row["vy"])) > 1e-7 or
                    not within_column):
                raise RuntimeError(f"{material} climbing tick {tick}: Java {row}, Horizon dy={dy} vy={vy}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--climb", action="store_true")
    args = parser.parse_args()
    rows = ladders.reference("climb" if args.climb else "wrench")
    run = climb if args.climb else exercise
    with fixture_world(args, "Metal Ladder Wrench", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 5 171 16 22 171 23 minecraft:stone",
            "/gamemode survival",
        ))
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-lad-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="metal-ladder-wrench", pack=args.pack,
            ) as guest:
                multiplayer.until("the ladder guest to join", lambda: any(
                    p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]
                ))
                host.command(f"/gamemode survival {GUEST}")
                run(host, guest, GUEST, rows)
        else:
            run(host, host, "@s", rows)
    measured = "climbing positions and active velocities" if args.climb else "Wrench block states and inventories"
    print(f"All {len(rows)} Metal Ladder {measured} match Java.")


if __name__ == "__main__":
    main()
