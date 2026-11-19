#!/usr/bin/env python3
"""Compare real survival Wand mirrored mining with the pinned Java event."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
wand = import_module("test-symmetry-wand-plane")
ITEM = "create:wand_of_symmetry"
PICK = "minecraft:iron_pickaxe"
ENV = {"HORIZON_NO_AUDIO": "1"}


def damage(host, player):
    result = host.command(f'/data get entity {player} SelectedItem.components."minecraft:damage"')
    match = re.search(r"entity data: (\d+)", result)
    return int(match[1]) if match else 0


def total_cobble(host, actor):
    return mp.count(actor, "minecraft:cobblestone") + sum(
        item["item"]["count"] for item in actor.call("entities", 32, "minecraft:item")["entities"]
        if item["item"]["item"] == "minecraft:cobblestone")


def run(args, scratch):
    with (ROOT / "fixtures/symmetry_wand_break-java.csv").open() as file:
        java = {row["case"]: row for row in csv.DictReader(file)}
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, "SymmetryWandBreak", render=not args.lan,
                                                    pack=args.pack, env=ENV))
        actor, player = host, "@s"
        if args.lan:
            player = "SymmetryMiner"
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            actor = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="symmetry-wand-break", pack=args.pack, env=ENV))
            mp.until("the guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]))
        host.commands((
            f"/gamemode survival {player}",
            "/fill 5 169 17 17 169 29 minecraft:stone",
            "/fill 5 170 17 17 174 29 minecraft:air",
            f"/tp {player} 10.5 170 25.5",
            f"/effect give {player} minecraft:haste 240 8 true",
            f"/item replace entity {player} hotbar.0 with {ITEM}[minecraft:custom_data={{marker:17}}]",
            "/tick unfreeze",
        ))
        mp.until("the Wand", lambda: mp.count(actor, ITEM) == 1)
        wand.activation(host, actor, player, (10, 169, 22), 0, (10, 170, 22))
        cases = (("xy", (10, 171, 24), (10, 171, 20), (10.5, 170, 26.5)),
                 ("mismatch", (11, 171, 24), (11, 171, 20), (11.5, 170, 26.5)),
                 ("empty_hand", (12, 171, 24), (12, 171, 20), (12.5, 170, 26.5)))
        for case, source, mirror, feet in cases:
            host.commands((f"/tp {player} {' '.join(map(str, feet))}",
                           f"/setblock {' '.join(map(str, source))} minecraft:stone",
                           f"/setblock {' '.join(map(str, mirror))} " + ("minecraft:dirt" if case == "mismatch" else "minecraft:stone")))
            if case != "empty_hand":
                host.command(f"/item replace entity {player} hotbar.1 with {PICK}")
                mp.until("the iron pickaxe", lambda: mp.count(actor, PICK) == 1)
                actor.call("select", PICK)
            else:
                actor.call("select", 3)
            mp.until("the mining position", lambda: abs(actor.call("state")["player"]["position"][0] - feet[0]) < .1)
            before = total_cobble(host, actor)
            actor.call("break", *source, "--timeout", 20)
            expected = java[case]["mirror_after"]
            mp.until(f"{case} mirrored block", lambda: host.call("block", *mirror)["block"] == expected)
            if case != "empty_hand":
                want = int(java[case]["tool_damage"]) + 1
                mp.until(f"{case} tool wear", lambda: damage(host, player) == want)
                expected_drops = int(java[case]["drop_count"]) + 1
                try:
                    mp.until(f"{case} cobblestone drops", lambda: total_cobble(host, actor) == before + expected_drops)
                except RuntimeError as error:
                    raise AssertionError((before, total_cobble(host, actor), actor.call("inventory"), host.call("entities", 32, "minecraft:item"))) from error
            else:
                mp.until("the empty-hand mirrored cobblestone", lambda: total_cobble(host, actor) == before + 1)
            print(f"{case}: mirrored block and tool wear match Java.", flush=True)
        host.command(f"/tp {player} 9.5 170 22.5")
        actor.call("look", -90, 0)
        actor.call("wait", 4)
        wand.activation(host, actor, player, (12, 169, 22), 1, (12, 170, 22))
        host.commands((f"/tp {player} 14.5 170 25.5", "/setblock 14 171 22 minecraft:stone",
                       "/setblock 10 171 22 minecraft:stone", f"/item replace entity {player} hotbar.1 with {PICK}"))
        mp.until("the YZ miner", lambda: abs(actor.call("state")["player"]["position"][0] - 14.5) < .1)
        actor.call("select", PICK)
        before = total_cobble(host, actor)
        actor.call("break", 14, 171, 22, "--timeout", 20)
        mp.until("the YZ reflected stone", lambda: host.call("block", 10, 171, 22)["block"] == java["yz"]["mirror_after"])
        mp.until("YZ tool wear", lambda: damage(host, player) == 2)
        mp.until("YZ cobblestone drops", lambda: total_cobble(host, actor) == before + 2)
        print("yz: mirrored block, source drops and tool wear match Java.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--lan", action="store_true")
    with TemporaryDirectory(prefix="hc-symbreak-", dir="/private/tmp") as scratch:
        run(parser.parse_args(), Path(scratch))
