#!/usr/bin/env python3
"""Insert items through a real Funnel into a configured Creative Crate."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
ENV = {"HORIZON_NO_AUDIO": "1"}


def run(args, scratch):
    with (ROOT / "fixtures/creative_crate_funnel-java.csv").open() as file:
        cases = list(csv.DictReader(file))
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, "CreativeCrateFunnel", render=not args.lan,
                                                    pack=args.pack, env=ENV))
        actor, player = host, "@s"
        if args.lan:
            player = "CrateFunnel"
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            actor = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="creative-crate-funnel", pack=args.pack, env=ENV))
            mp.until("the guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]))
        host.commands((f"/gamemode survival {player}",
                       "/fill 5 169 17 15 169 27 minecraft:stone",
                       "/fill 5 170 17 15 175 27 minecraft:air",
                       "/setblock 9 170 24 minecraft:stone",
                       "/setblock 9 171 22 create:creative_crate",
                       f"/tp {player} 9.5 171 24.5",
                       f"/item replace entity {player} hotbar.0 with minecraft:iron_ingot 7"))
        mp.until("the iron sample", lambda: mp.count(actor, "minecraft:iron_ingot") == 7)
        actor.call("select", "minecraft:iron_ingot")
        actor.call("look-at", 9.5, 172, 22.5)
        mp.until("the crate top", lambda: (hit := actor.call("looking-at").get("block"))
                 and hit["pos"] == [9, 171, 22] and hit["face"] == "up")
        actor.call("mouse", "right", "click")
        def filtered():
            data = host.command("/data get block 9 171 22 Filter")
            return '"minecraft:iron_ingot"' in data and 'count: 7' in data
        mp.until("the crate supply filter", filtered)
        host.commands(("/setblock 10 171 22 create:andesite_funnel[facing=east,extracting=false] strict",
                       "/setblock 12 170 22 minecraft:stone",
                       f"/tp {player} 12.5 171 22.5"))
        mp.until("the Funnel operator", lambda: abs(actor.call("state")["player"]["position"][0] - 12.5) < .1)
        for case in cases:
            host.command(f"/item replace entity {player} hotbar.1 with minecraft:gold_ingot 5")
            mp.until("the five gold to insert", lambda: mp.count(actor, "minecraft:gold_ingot") == 5)
            actor.call("select", "minecraft:gold_ingot")
            actor.call("look-at", 10.65, 171.5, 22.5)
            mp.until("the Funnel mouth", lambda: (hit := actor.call("looking-at").get("block"))
                     and hit["pos"] == [10, 171, 22] and hit["face"] == "east")
            interaction = actor.call("mouse", "right", "click")
            try:
                mp.until("the Funnel to accept the gold", lambda: mp.count(actor, "minecraft:gold_ingot") == int(case["held_count"]))
            except RuntimeError as error:
                raise AssertionError((interaction, actor.call("looking-at"), actor.call("state")["player"], actor.call("inventory"), host.call("block", 10, 171, 22), host.command("/data get block 9 171 22"))) from error
            assert filtered(), host.command("/data get block 9 171 22 Filter")
            print(f'Use {case["use"]}: five gold accepted; seven-iron crate filter retained.', flush=True)
        host.commands(("/setblock 10 170 22 create:depot",
                       "/setblock 10 171 22 create:brass_belt_funnel[facing=east,shape=pushing] strict"))
        start = host.clock()
        for tick in range(1, 25):
            host.step_to(start + tick)
            data = host.command("/data get block 10 170 22 Items")
            if '"minecraft:iron_ingot"' in data:
                break
        else:
            raise AssertionError(("supply after insertion", data))
        assert 'count: 64' in data and filtered(), data
        print("After both insertions the crate still supplies iron through a Brass Funnel.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--lan", action="store_true")
    with TemporaryDirectory(prefix="hc-crate-funnel-", dir="/private/tmp") as scratch:
        run(parser.parse_args(), Path(scratch))
