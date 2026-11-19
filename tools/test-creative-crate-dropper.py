#!/usr/bin/env python3
"""Compare a Dropper feeding a Creative Crate and a Dropper facing air."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
count_in = import_module("test-creative-crate-hopper").tagged_count
ENV = {"HORIZON_NO_AUDIO": "1"}
GOLD = "minecraft:gold_ingot"
IRON = "minecraft:iron_ingot"


def run(args, scratch):
    with (ROOT / "fixtures/creative_crate_dropper-java.csv").open() as file:
        expected = list(csv.DictReader(file))
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(
            args, "CreativeCrateDropper", render=not args.lan, pack=args.pack, env=ENV))
        actor, player = host, "@s"
        if args.lan:
            player = "CrateDropper"
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            actor = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="crate-dropper", pack=args.pack, env=ENV))
            mp.until("guest joins", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]))
        host.commands((
            f"/gamemode survival {player}",
            "/fill 5 170 19 17 170 30 minecraft:stone",
            "/fill 5 171 19 17 175 30 minecraft:air",
            "/setblock 9 171 22 create:creative_crate",
            f"/tp {player} 9.5 171 24.5",
            f"/item replace entity {player} hotbar.0 with {GOLD} 7",
            "/setblock 8 171 22 minecraft:dropper[facing=east] strict",
            "/setblock 8 171 27 minecraft:dropper[facing=east] strict",
            f"/item replace block 8 171 22 container.0 with {IRON} 3",
            f"/item replace block 8 171 27 container.0 with {IRON} 3",
        ))
        if args.lan:
            host.command("/tp @s 12.5 171 25.5")
        mp.until("the gold sample reaches the player", lambda: mp.count(actor, GOLD) == 7)
        actor.call("select", GOLD)
        actor.call("look-at", 9.5, 172, 22.5)
        mp.until("the Crate top is targeted", lambda: (hit := actor.call("looking-at").get("block"))
                 and hit["pos"] == [9, 171, 22] and hit["face"] == "up")
        actor.call("mouse", "right", "click")
        mp.until("the gold sample enters the Crate filter",
                 lambda: count_in(host.command("/data get block 9 171 22 Filter"), GOLD) == 7)
        host.commands(("/setblock 7 171 22 minecraft:redstone_block",
                       "/setblock 7 171 27 minecraft:redstone_block"))
        start = host.clock()
        now = 0
        differences = []
        for row in expected:
            tick = int(row["tick"])
            if tick > now:
                host.step_to(start + tick)
                now = tick
            crate = row["lane"] == "crate"
            z = 22 if crate else 27
            count = count_in(host.command(f"/data get block 8 171 {z} Items"), IRON)
            drops = sum(abs(entity["pos"][2] - (z + 0.5)) < 2 for entity in
                        host.call("entities", 35, "minecraft:item")["entities"])
            sample = count_in(host.command("/data get block 9 171 22 Filter"), GOLD) if crate else 0
            actual = (count, drops, sample)
            wanted = tuple(int(row[key]) for key in ("slot", "drops", "filter"))
            if actual != wanted:
                differences.append((row["lane"], tick, actual, wanted))
        assert not differences, differences
        assert mp.count(actor, GOLD) == 7
        print(f"Both Dropper lanes matched {len(expected)} Java observations.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--lan", action="store_true")
    with TemporaryDirectory(prefix="hc-crate-drop-", dir="/private/tmp") as scratch:
        run(parser.parse_args(), Path(scratch))
