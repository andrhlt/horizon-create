#!/usr/bin/env python3
"""Exercise real single-plane Wand activation and Survival block mirroring."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
WAND = "create:wand_of_symmetry"
GUEST = "SymmetryGuest"
ENV = {"HORIZON_NO_AUDIO": "1"}


def selected(host, player):
    return host.command(f"/data get entity {player} SelectedItem")


def activation(host, actor, player, clicked, axis, anchor):
    actor.call("select", WAND)
    actor.call("interact", *clicked, "up")
    expected = f'position: [{anchor[0]}.0d, {anchor[1]}.0d, {anchor[2]}.0d]'
    def stored():
        data = selected(host, player)
        parts = ('"create:symmetry_wand"', '"create:symmetry_wand_enable": 1b',
                 'type: "plane"', f'orientation_index: {axis}', expected, 'marker: 17')
        return data if all(part in data for part in parts) else None
    try:
        mp.until("the activated Wand's plane", stored)
    except RuntimeError as error:
        raise AssertionError(selected(host, player)) from error


def place(host, actor, source, mirrored, count, expected_mirror):
    actor.call("select", "minecraft:stone")
    actor.call("interact", source[0], source[1] - 1, source[2], "up")
    mp.until("the original stone to be placed", lambda: host.call("block", *source)["block"] == "minecraft:stone")
    if expected_mirror:
        mp.until("the reflected stone to appear", lambda: host.call("block", *mirrored)["block"] == "minecraft:stone")
    elif host.call("block", *mirrored)["block"] != "minecraft:air":
        raise RuntimeError(f"Unexpected reflected block: {host.call('block', *mirrored)}")
    mp.until("the correct stone consumption", lambda: mp.count(actor, "minecraft:stone") == count)


def run(args, scratch):
    with (ROOT / "fixtures/symmetry_wand_plane-java.csv").open() as data:
        java = {row["case"]: row for row in csv.DictReader(data)}
    assert java["xy"]["orientation_index"] == "0" and java["yz"]["orientation_index"] == "1"
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, "SymmetryWandPlane", render=not args.lan,
                                                    pack=args.pack, env=ENV))
        actor, player = host, "@s"
        if args.lan:
            player = GUEST
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            actor = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="symmetry-wand-plane", pack=args.pack, env=ENV))
            mp.until("the guest to join", lambda: any(
                p["name"] == player and p["placed"] for p in host.call("lan", "status")["guests"]))
        host.command(f"/gamemode survival {player}")
        host.commands((
            "/fill 4 169 17 17 169 29 minecraft:stone",
            "/fill 4 170 17 17 175 29 minecraft:air",
            f"/tp {player} 10.5 170 25.5",
            f"/item replace entity {player} hotbar.0 with {WAND}[minecraft:custom_data={{marker:17}}]",
            f"/item replace entity {player} hotbar.1 with minecraft:stone 4",
        ))
        mp.until("the Wand to reach the player", lambda: mp.count(actor, WAND) == 1)
        mp.until("the player to face the mirror support", lambda: actor.call("state")["player"]["position"] == [10.5, 170.0, 25.5])
        activation(host, actor, player, (10, 169, 22), 0, (10, 170, 22))
        place(host, actor, (10, 170, 24), (10, 170, 20), 2, True)
        host.command(f"/item replace entity {player} hotbar.1 with minecraft:stone 1")
        mp.until("the single stone to reach the player", lambda: mp.count(actor, "minecraft:stone") == 1)
        host.command(f"/tp {player} 11.5 170 25.5")
        mp.until("the player to reach the single-stone placement", lambda: actor.call("state")["player"]["position"] == [11.5, 170.0, 25.5])
        place(host, actor, (11, 170, 24), (11, 170, 20), 0, False)
        actor.call("select", WAND)
        actor.call("look", 0, -90)
        actor.call("use-item")
        def disabled():
            data = selected(host, player)
            return data if '"create:symmetry_wand_enable": 0b' in data and 'type: "plane"' in data else None
        mp.until("the Wand to retain its plane while disabled", disabled)
        host.command(f"/item replace entity {player} hotbar.1 with minecraft:stone 3")
        mp.until("the stone to reach the player", lambda: mp.count(actor, "minecraft:stone") == 3)
        host.command(f"/tp {player} 12.5 170 25.5")
        mp.until("the player to reach the disabled placement", lambda: actor.call("state")["player"]["position"] == [12.5, 170.0, 25.5])
        place(host, actor, (12, 170, 24), (12, 170, 20), 2, False)
        host.command(f"/tp {player} 9.5 170 22.5")
        mp.until("the player to reach the second support", lambda: actor.call("state")["player"]["position"] == [9.5, 170.0, 22.5])
        actor.call("look", -90, 0)
        actor.call("wait", 4)
        activation(host, actor, player, (12, 169, 22), 1, (12, 170, 22))
        host.command(f"/tp {player} 14.5 170 25.5")
        mp.until("the player to reach the placement side", lambda: actor.call("state")["player"]["position"] == [14.5, 170.0, 25.5])
        place(host, actor, (14, 170, 22), (10, 170, 22), 0, True)
    print("Survival Wand activation, both plane axes, extra-block use, insufficient supplies, and air deactivation matched the Java oracle.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--lan", action="store_true")
    with TemporaryDirectory(prefix="hc-symmetry-wand-") as scratch:
        run(parser.parse_args(), Path(scratch))
