#!/usr/bin/env python3
"""Exercise Extendo Grip block reach with survival crosshair and mouse controls.

Expected reach bands use the pinned Java ExtendoGripItem survival attribute
oracle (+3 for either hand, +5 for both). This compares gameplay controls in
Horizon with Java attribute values, not Java mouse-control traces.
"""
import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

mp = import_module("test-multiplayer")
GRIP = "create:extendo_grip"
FEET = (8.5, 171, 25.5)
# The note block's near face is 3.5, 6.5, 8.5 or 10.5 blocks from the eye.
TARGETS = (21, 18, 16, 14)
CASES = (("neither", False, False, 1), ("main", True, False, 2),
         ("off", False, True, 2), ("dual", True, True, 3))


def exercise(world, actor, player, cases):
    world.commands((
        "/fill 6 171 12 11 174 27 minecraft:air",
        "/fill 6 170 12 11 170 27 minecraft:stone",
        f"/tp {player} {' '.join(map(str, FEET))}",
        f"/gamemode survival {player}",
    ))
    mp.until("the player to stand at the reach fixture", lambda:
             actor.call("state")["player"]["position"] == list(FEET))
    for case, main, off, in_range in cases:
        world.commands((
            f"/item replace entity {player} weapon.mainhand with {GRIP if main else 'minecraft:air'}",
            f"/item replace entity {player} weapon.offhand with {GRIP if off else 'minecraft:air'}",
        ))
        actor.call("wait", 5)
        held = (actor.call("inventory")["held"] or {}).get("item")
        expected_main = GRIP if main else None
        assert held == expected_main, (case, held, actor.call("inventory"))
        off_data = world.command(f"/data get entity {player} equipment.offhand")
        assert (GRIP in off_data) == off, (case, off_data)
        for index, z in enumerate(TARGETS):
            pos = (8, 172, z)
            world.command(f"/setblock 8 172 {z} minecraft:note_block")
            mp.until("the note block to reach the actor", lambda: actor.call("block", *pos)["block"] == "minecraft:note_block")
            actor.call("look-at", 8.5, 172.62, z + 0.99)
            actor.call("wait", 2)
            hit = actor.call("looking-at")
            targeted = (hit.get("block") or {}).get("pos") == list(pos)
            expected = index < in_range
            if targeted != expected:
                raise AssertionError(f"{case}, target {pos}, expected targeted={expected}: {hit}, inventory={actor.call("inventory")}")
            actor.call("mouse", "right", "click")
            actor.call("wait", 4)
            state = world.call("block", *pos)["state"]
            changed = "note=1" in state
            if changed != expected:
                raise AssertionError(f"{case}, target {pos}, expected note changed={expected}: {state}")
            world.command(f"/setblock 8 172 {z} minecraft:air")
        print(f"{case}: {in_range} reachable bands passed", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, "ExtendoReach", render=True, pack=args.pack))
        actor, player = world, "@s"
        if args.lan:
            world.command("/tp @s 4.5 171 27.5")
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-extendo-lan-")))
            player = "ExtendoGuest"
            actor = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="extendo-reach", pack=args.pack,
            ))
            mp.until("the guest to join", lambda: any(
                entry["name"] == player and entry["placed"]
                for entry in world.call("lan", "status")["guests"]
            ))
        exercise(world, actor, player, CASES[:1] if args.baseline_only else CASES)
    print("Survival controls agree with the Java attribute oracle reach bands.")


if __name__ == "__main__":
    main()
