#!/usr/bin/env python3
"""Compare vanilla Hopper transfers against a configured Creative Crate."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
ENV = {"HORIZON_NO_AUDIO": "1"}


def tagged_count(data, item):
    match = re.search(r"count: (\d+)", data)
    return int(match[1]) if match and f'"{item}"' in data else 0


def run(args, scratch):
    with (ROOT / "fixtures/creative_crate_hopper-java.csv").open() as file:
        expected = [row for row in csv.DictReader(file) if row["case"] == args.case]
    assert expected, args.case
    with ExitStack() as sessions:
        host = sessions.enter_context(fixture_world(args, "CreativeCrateHopper", render=not args.lan,
                                                    pack=args.pack, env=ENV))
        actor, player = host, "@s"
        if args.lan:
            player = "CrateHopper"
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            actor = sessions.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario="creative-crate-hopper", pack=args.pack, env=ENV))
            mp.until("guest joins", lambda: any(
                guest["name"] == player and guest["placed"] for guest in host.call("lan", "status")["guests"]))
        host.commands((
            f"/gamemode survival {player}",
            "/fill 5 169 17 15 169 27 minecraft:stone",
            "/fill 5 170 17 15 175 27 minecraft:air",
            "/setblock 9 170 24 minecraft:stone",
            "/setblock 9 171 22 create:creative_crate",
            f"/tp {player} 9.5 171 24.5",
            f"/item replace entity {player} hotbar.0 with minecraft:iron_ingot[minecraft:custom_data={{marker:17}}] 7",
        ))
        mp.until("tagged iron enters the hotbar", lambda: mp.count(actor, "minecraft:iron_ingot") == 7)
        actor.call("select", 3 if args.case == "empty" else "minecraft:iron_ingot")
        actor.call("look-at", 9.5, 172, 22.5)
        mp.until("actor aims at crate top", lambda: (hit := actor.call("looking-at").get("block"))
                 and hit["pos"] == [9, 171, 22] and hit["face"] == "up")
        actor.call("mouse", "right", "click")
        if args.case != "empty":
            mp.until("tagged filter is installed", lambda: "marker: 17" in
                     host.command("/data get block 9 171 22 Filter"))
        host.commands((
            "/setblock 9 170 22 minecraft:hopper[facing=down] strict",
            "/setblock 8 171 22 minecraft:hopper[facing=east] strict",
            "/item replace block 8 171 22 container.0 with minecraft:gold_ingot 5",
        ))
        if args.case == "powered":
            host.commands((
                "/setblock 10 170 22 minecraft:redstone_block",
                "/setblock 7 171 22 minecraft:redstone_block",
            ))
        if args.case == "full":
            host.commands(
                f"/item replace block 9 170 22 container.{slot} with minecraft:cobblestone 64"
                for slot in range(5)
            )
        start = host.clock()
        differences = []
        for row in expected:
            tick = int(row["tick"])
            if tick:
                host.step_to(start + tick)
            pull, push, sample = host.commands((
                "/data get block 9 170 22 Items",
                "/data get block 8 171 22 Items",
                "/data get block 9 171 22 Filter",
            ))
            got = (tagged_count(pull, "minecraft:iron_ingot"), tagged_count(push, "minecraft:gold_ingot"),
                   "marker: 17" in pull, tagged_count(sample, "minecraft:iron_ingot"),
                   tagged_count(pull, "minecraft:cobblestone"))
            want = (int(row["pull"]), int(row["push"]), row["tagged"] == "true",
                    int(row["filter_count"]), int(row["cobblestone"]))
            if got != want:
                differences.append((tick, got, want))
        assert not differences, differences
        assert mp.count(actor, "minecraft:iron_ingot") == 7
        print(f"{args.case}: all {len(expected)} Java Hopper samples matched, and the held stack stayed intact.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--case", choices=("ordinary", "empty", "powered", "full"), default="ordinary")
    with TemporaryDirectory(prefix="hc-crate-hopper-", dir="/private/tmp") as scratch:
        run(parser.parse_args(), Path(scratch))
