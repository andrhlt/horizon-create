#!/usr/bin/env python3
"""Exercise grip wear on single-block and multi-block survival placements."""
import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from fixture_world import fixture_world

mp = import_module("test-multiplayer")
GRIP = "create:extendo_grip"


def run(world, actor, player, baseline):
    world.commands((
        "/fill 6 170 12 11 170 27 minecraft:stone",
        "/fill 6 171 12 11 175 27 minecraft:air",
        f"/tp {player} 8.5 171 25.5",
        f"/gamemode survival {player}",
    ))
    for case, item, expected in (("stone", "minecraft:stone", "minecraft:stone"),
                                  ("door", "minecraft:oak_door", "minecraft:oak_door"),
                                  ("blocked", "minecraft:oak_door", None)):
        world.commands((
            "/fill 8 171 22 8 173 22 minecraft:air",
            "/setblock 8 172 14 minecraft:stone",
            f"/item replace entity {player} hotbar.0 with {item}",
            f"/item replace entity {player} weapon.offhand with {GRIP}",
        ))
        actor.call("key", "1", "tap")
        mp.until("the building item and grip", lambda:
                 (actor.call("inventory")["held"] or {}).get("item") == item and
                 actor.call("inventory")["offhand"]["item"] == GRIP)
        if not expected:
            world.commands(("/setblock 8 171 22 minecraft:stone", "/setblock 8 173 22 minecraft:stone"))
        target = (8, 170, 22) if expected else (8, 171, 22)
        actor.call("look-at", *((8.5, 171.0, 22.5) if expected else (8.5, 172.0, 22.5)))
        actor.call("wait", 3)
        hit = actor.call("looking-at")
        assert (hit.get("block") or {}).get("pos") == list(target), (case, hit)
        actor.call("mouse", "right", "click")
        actor.call("wait", 4)
        if expected:
            mp.until("the placed block on the host", lambda: world.call("block", 8, 171, 22)["block"] == expected)
            if case == "door":
                assert world.call("block", 8, 172, 22)["block"] == expected
        else:
            assert world.call("block", 8, 172, 22)["block"] == "minecraft:air"
        reply = world.command(f'/data get entity {player} equipment.offhand.components."minecraft:damage"')
        match = re.search(r"entity data: (\d+)", reply)
        damage = int(match[1]) if match else 0
        want = 0 if baseline or not expected else 1
        assert damage == want, (case, damage, want, reply)
        print(f"{case}: grip damage={damage}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, "ExtendoPlace", render=True, pack=args.pack))
        actor, player = world, "@s"
        if args.lan:
            world.command("/tp @s 4.5 171 27.5")
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-extendo-place-lan-")))
            player = "ExtendoGuest"
            actor = stack.enter_context(mp.joined_client(args, scratch, f"127.0.0.1:{port}", player,
                                      render=True, scenario="extendo-place", pack=args.pack))
            mp.until("the guest to join", lambda: any(entry["name"] == player and entry["placed"]
                     for entry in world.call("lan", "status")["guests"]))
        run(world, actor, player, args.baseline)


if __name__ == "__main__":
    main()
