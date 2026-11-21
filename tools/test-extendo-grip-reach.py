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


def exercise(world, actor, player, cases, stack, args, port=None):
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

    # Entity targeting uses Horizon's separate entity interaction range. Java
    # extends that ray to its block interaction range while either grip is held.
    world.commands((
        "/fill 6 171 12 11 174 27 minecraft:air",
        "/fill 6 170 12 11 170 27 minecraft:stone",
        f"/tp {player} {' '.join(map(str, FEET))}",
    ))
    mp.until("the player to return to the entity reach fixture", lambda:
             actor.call("state")["player"]["position"] == list(FEET))
    for case, main, off, target_z, expected in (("entity_none", False, False, 18.5, False),
                                                ("entity_main", True, False, 18.5, True),
                                                ("entity_off", False, True, 18.5, True),
                                                ("entity_dual", True, True, 16.5, True)):
        world.commands((
            "/kill @e[tag=extendo_entity_target]",
            f"/summon minecraft:pig 8.5 171 {target_z} {{NoAI:1b,NoGravity:1b,Tags:[\"extendo_entity_target\"]}}",
            f"/item replace entity {player} weapon.mainhand with {GRIP if main else 'minecraft:air'}",
            f"/item replace entity {player} weapon.offhand with {GRIP if off else 'minecraft:air'}",
        ))
        actor.call("wait", 5)
        world.command("/tick unfreeze")
        actor.call("wait", 4)
        world.command("/tick freeze")
        actor.call("look-at", 8.5, 171.5, target_z + 0.7)
        actor.call("wait", 2)
        hit = actor.call("looking-at")
        targeted = hit.get("kind") == "entity" and (hit.get("entity") or {}).get("type") == "minecraft:pig"
        if targeted != expected:
            raise AssertionError(f"{case}: expected entity targeted={expected}: {hit}")
        if actor is not world and expected:
            world.command("/tick unfreeze")
            actor.call("wait", 14)
            actor.call("mouse", "left", "click")
            actor.call("wait", 8)
            world.command("/tick freeze")
            health = world.command("/data get entity @e[tag=extendo_entity_target,limit=1] Health")
            if "9.0f" not in health:
                raise AssertionError(f"{case}: host did not apply the guest's entity attack: {health}")
            world.command("/data merge entity @e[tag=extendo_entity_target,limit=1] {Health:10.0f}")
        print(f"{case}: entity targeting {'passed' if targeted == expected else 'failed'}", flush=True)

    if actor is world:
        # The grip is inventory state, not a saved attribute modifier. Reopen
        # with both grips equipped, then verify removing them removes reach.
        world.restart()
        actor = world
        player = "@s"
        mp.until("the dual grips to remain equipped after reopen", lambda:
                 (actor.call("inventory")["held"] or {}).get("item") == GRIP and
                 actor.call("inventory")["offhand"]["item"] == GRIP)
        world.command("/tick unfreeze")
        actor.call("wait", 4)
        world.command("/tick freeze")
        actor.call("look-at", 8.5, 171.5, 17.2)
        actor.call("wait", 2)
        hit = actor.call("looking-at")
        if hit.get("kind") != "entity" or (hit.get("entity") or {}).get("type") != "minecraft:pig":
            raise AssertionError(f"Dual-grip entity reach did not survive world reopen: {hit}")
        world.commands((
            f"/item replace entity {player} weapon.mainhand with minecraft:air",
            f"/item replace entity {player} weapon.offhand with minecraft:air",
        ))
        actor.call("wait", 5)
        actor.call("look-at", 8.5, 171.5, 17.2)
        actor.call("wait", 2)
        hit = actor.call("looking-at")
        if hit.get("kind") == "entity" and (hit.get("entity") or {}).get("type") == "minecraft:pig":
            raise AssertionError(f"Entity reach remained extended after unequipping across reopen: {hit}")
        print("dual grips survived world reopen and unequipping removed entity reach", flush=True)
    else:
        # An offline guest's inventory is saved when it leaves. Rejoin using
        # the same player name, verify the equipped grip still works, then
        # remove it and ensure the server/client do not retain a reach bonus.
        actor.call("quit")
        mp.until("the guest to leave", lambda: not any(
            entry["name"] == player for entry in world.call("lan", "status")["guests"]
        ))
        guest_scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-extendo-rejoin-")))
        actor = stack.enter_context(mp.joined_client(
            args, guest_scratch, f"127.0.0.1:{port}", player,
            render=True, scenario="extendo-rejoin", pack=args.pack,
        ))
        mp.until("the guest to rejoin", lambda: any(
            entry["name"] == player and entry["placed"]
            for entry in world.call("lan", "status")["guests"]
        ))
        mp.until("the saved dual grips to return", lambda:
                 (actor.call("inventory")["held"] or {}).get("item") == GRIP and
                 actor.call("inventory")["offhand"]["item"] == GRIP)
        world.command("/tick unfreeze")
        actor.call("wait", 4)
        world.command("/tick freeze")
        actor.call("wait", 2)
        actor.call("look-at", 8.5, 171.5, 17.2)
        actor.call("wait", 2)
        hit = actor.call("looking-at")
        if hit.get("kind") != "entity" or (hit.get("entity") or {}).get("type") != "minecraft:pig":
            raise AssertionError(f"Rejoined guest lost equipped-grip entity reach: {hit}")
        world.command(f"/item replace entity {player} weapon.mainhand with minecraft:air")
        world.command(f"/item replace entity {player} weapon.offhand with minecraft:air")
        actor.call("wait", 5)
        world.command("/tick unfreeze")
        actor.call("wait", 4)
        world.command("/tick freeze")
        actor.call("look-at", 8.5, 171.5, 17.2)
        actor.call("wait", 2)
        hit = actor.call("looking-at")
        if hit.get("kind") == "entity" and (hit.get("entity") or {}).get("type") == "minecraft:pig":
            raise AssertionError(f"Guest retained entity reach after unequipping post-rejoin: {hit}")
        print("LAN guest retained equipped reach after rejoin and lost it after unequipping", flush=True)


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
        exercise(world, actor, player, CASES[:1] if args.baseline_only else CASES, stack, args,
                 port if args.lan else None)
    print("Survival controls agree with the Java attribute oracle reach bands.")


if __name__ == "__main__":
    main()
