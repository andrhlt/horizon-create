#!/usr/bin/env python3
"""Configure a Creative Crate by its value box and extract twice through a Funnel."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
ENV = {"HORIZON_NO_AUDIO": "1"}
CRATE = (9, 171, 22)
DEPOT = (10, 170, 22)


def run(args, scratch):
    with (ROOT / "fixtures/creative_crate_supply-java.csv").open() as file:
        java = next(row for row in csv.DictReader(file) if int(row["extract_second"]) == args.limit)
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, "CreativeCrateSupply", render=not args.lan,
                                                    pack=args.pack, env=ENV))
        actor, player = host, "@s"
        if args.lan:
            player = "CrateGuest"
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            actor = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="creative-crate", pack=args.pack, env=ENV))
            mp.until("the guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]))
        filter_components = "minecraft:custom_data={marker:17}"
        if args.limit != 64:
            filter_components += f",minecraft:max_stack_size={args.limit}"
        host.commands((
            f"/gamemode survival {player}",
            "/fill 5 169 17 15 169 27 minecraft:stone",
            "/fill 5 170 17 15 175 27 minecraft:air",
            "/setblock 9 170 24 minecraft:stone",
            "/setblock 9 171 22 create:creative_crate",
            f"/tp {player} 9.5 171 24.5",
            f"/item replace entity {player} hotbar.0 with minecraft:iron_ingot[{filter_components}] {java['held_count']}",
        ))
        mp.until("the iron sample", lambda: mp.count(actor, "minecraft:iron_ingot") == int(java["held_count"]))
        mp.until("the player to stand above the crate", lambda: abs(actor.call("state")["player"]["position"][1] - 171) < .1)
        actor.call("select", "minecraft:iron_ingot")
        actor.call("look-at", 9.5, 172, 22.5)
        mp.until("the top of the crate", lambda: (hit := actor.call("looking-at").get("block"))
                 and hit["pos"] == list(CRATE) and hit["face"] == "up")
        actor.call("mouse", "right", "click")
        def filter_data():
            data = host.command("/data get block 9 171 22 Filter")
            required = ['"minecraft:iron_ingot"', f"count: {java['filter_count']}", "marker: 17"]
            if args.limit != 64:
                required.append(f'"minecraft:max_stack_size": {args.limit}')
            return data if all(part in data for part in required) else None
        try:
            mp.until("the Java-shaped crate filter", filter_data)
        except RuntimeError as error:
            raise AssertionError(host.command("/data get block 9 171 22")) from error
        assert mp.count(actor, "minecraft:iron_ingot") == 7
        host.commands(("/setblock 10 170 22 create:depot",
                       "/setblock 10 171 22 create:brass_belt_funnel[facing=east,shape=pushing] strict"))
        if args.exact:
            exact_count = int(java["exact_below"])
            host.command(f"/data merge block 10 171 22 {{FilterAmount:{args.limit + 1},UpTo:0b}}")
            start = host.clock()
            for tick in range(1, 25):
                host.step_to(start + tick)
                data = host.command("/data get block 10 170 22 Items")
                assert '"minecraft:iron_ingot"' not in data, (tick, data)
            assert java["exact_above"] == "0"
            host.command(f"/data merge block 10 171 22 {{FilterAmount:{exact_count},UpTo:0b}}")
        expected_count = exact_count if args.exact else int(java["extract_second"])
        for cycle in range(2):
            start = host.clock()
            for tick in range(1, 25):
                host.step_to(start + tick)
                data = host.command("/data get block 10 170 22 Items")
                if '"minecraft:iron_ingot"' in data:
                    break
            else:
                raise AssertionError((cycle, data, host.command("/data get block 9 171 22")))
            assert f"count: {expected_count}" in data and 'marker: 17' in data, data
            if args.limit != 64:
                assert f'"minecraft:max_stack_size": {args.limit}' in data, data
            assert filter_data(), host.command("/data get block 9 171 22 Filter")
            print(f"Extraction {cycle + 1}: {expected_count} tagged iron, filter and held sample retained.", flush=True)
            if cycle == 0:
                host.command("/data merge block 10 170 22 {Items:[]}")
        actor.call("select", 3)
        actor.call("look-at", 9.5, 172, 22.5)
        mp.until("the crate top to clear", lambda: (hit := actor.call("looking-at").get("block"))
                 and hit["pos"] == list(CRATE) and hit["face"] == "up")
        actor.call("mouse", "right", "click")
        mp.until("the empty filter", lambda: '"minecraft:iron_ingot"' not in host.command("/data get block 9 171 22 Filter"))
        print("Empty-hand interaction cleared the crate filter.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--limit", type=int, choices=(64, 16), default=64)
    parser.add_argument("--exact", action="store_true")
    args = parser.parse_args()
    if args.exact and args.limit != 16:
        parser.error("--exact requires --limit 16")
    with TemporaryDirectory(prefix="hc-creative-crate-", dir="/private/tmp") as scratch:
        run(args, Path(scratch))
