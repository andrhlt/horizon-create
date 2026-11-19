#!/usr/bin/env python3
"""Exercise survival Extendo Grip wear on a real mouse-driven block break."""
import argparse
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
import re

from fixture_world import fixture_world

mp = import_module("test-multiplayer")
GRIP = "create:extendo_grip"
POS = (8, 172, 22)


def damage(world, player, path):
    result = world.command(f'/data get entity {player} {path}.components."minecraft:damage"')
    match = re.search(r"entity data: (\d+)", result)
    return int(match[1]) if match else 0


def run(world, actor, player, baseline):
    world.commands((
        "/fill 6 170 20 11 170 27 minecraft:stone",
        "/fill 6 171 20 11 174 27 minecraft:air",
        f"/tp {player} 8.5 171 25.5",
        f"/gamemode survival {player}",
    ))
    cases = (("main", True, False, None, 1, 0, None),
             ("off", False, True, None, 0, 1, None),
             ("dual", True, True, None, 1, 0, None),
             ("air_900", True, False, 900, 0, 0, 899),
             ("air_1", True, False, 1, 0, 0, 0),
             ("air_0", True, False, 0, 1, 0, 0))
    for name, main, off, air, want_main, want_off, want_air in cases[:1] if baseline else cases:
        world.commands((
            f"/item replace entity {player} hotbar.0 with minecraft:air",
            f"/item replace entity {player} weapon.offhand with minecraft:air",
            f"/item replace entity {player} armor.chest with minecraft:air",
        ))
        actor.call("key", "1", "tap")
        if air is not None:
            world.command("/setblock 9 171 24 create:copper_backtank")
            reply = world.command(f"/data merge block 9 171 24 {{Air:{air}}}")
            assert "Modified block data" in reply, reply
            actor.call("interact", 9, 171, 24, "up")
            tank = mp.until("the charged backtank to be equipped", lambda:
                            (value if 'create:copper_backtank' in (value := world.command(f"/data get entity {player} equipment.chest")) else None))
            assert f'"create:banktank_air": {air}' in tank, tank
        world.commands((
            f"/item replace entity {player} hotbar.0 with {GRIP if main else 'minecraft:air'}",
            f"/item replace entity {player} weapon.offhand with {GRIP if off else 'minecraft:air'}",
            "/setblock 8 172 22 minecraft:dirt",
        ))
        mp.until("the correct hands", lambda:
                 ((actor.call("inventory")["held"] or {}).get("item") == (GRIP if main else None)) and
                 (actor.call("inventory")["offhand"]["item"] == (GRIP if off else None)))
        actor.call("look-at", 8.5, 172.5, 22.99)
        assert (actor.call("looking-at").get("block") or {}).get("pos") == list(POS)
        actor.call("mouse", "left", "down")
        try:
            for _ in range(60):
                world.step_to(world.clock() + 1)
                actor.call("wait", 1)
                if world.call("block", *POS)["block"] == "minecraft:air":
                    break
            else:
                raise AssertionError("The player did not break the dirt block")
        finally:
            actor.call("mouse", "left", "up")
        actor.call("wait", 4)
        actual_main = damage(world, player, "SelectedItem") if main else 0
        actual_off = damage(world, player, "equipment.offhand") if off else 0
        if baseline:
            want_main = 0
        assert (actual_main, actual_off) == (want_main, want_off), (name, actual_main, actual_off, want_main, want_off)
        if air is not None:
            tank = world.command(f'/data get entity {player} equipment.chest.components."create:banktank_air"')
            found = re.search(r"entity data: (\d+)", tank)
            actual_air = int(found[1]) if found else 0
            assert actual_air == want_air, (name, actual_air, want_air, tank)
        print(f"{name}: main={actual_main}, off={actual_off}, air={want_air}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--baseline", action="store_true", help="reproduce missing-wear behavior")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, "ExtendoWear", render=True, pack=args.pack))
        actor, player = world, "@s"
        if args.lan:
            world.command("/tp @s 4.5 171 27.5")
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-extendo-wear-lan-")))
            player = "ExtendoGuest"
            actor = stack.enter_context(mp.joined_client(args, scratch, f"127.0.0.1:{port}", player,
                                      render=True, scenario="extendo-wear", pack=args.pack))
            mp.until("the guest to join", lambda: any(entry["name"] == player and entry["placed"]
                     for entry in world.call("lan", "status")["guests"]))
        run(world, actor, player, args.baseline)


if __name__ == "__main__":
    main()
