#!/usr/bin/env python3
"""Replay Java's placement, stacking and support removal for all metal scaffolding."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
MATERIALS = ("andesite", "brass", "copper")


def stonecut(args):
    bars = import_module("test-metal-bars")
    with (ROOT / "fixtures/metal-scaffolding-recipe-java.csv").open(newline="") as stream:
        recipes = list(csv.DictReader(stream))
    env = {"HORIZON_NO_AUDIO": "1"}
    with fixture_world(args, "MetalScaffoldingStonecutter", render=True, pack=args.pack, env=env) as host:
        host.commands((
            "/fill 8 170 22 14 170 28 minecraft:stone",
            "/setblock 11 171 24 minecraft:stonecutter",
            "/tp @s 11.5 171 26.5",
            "/gamemode survival",
        ))
        for slot, recipe in enumerate(recipes):
            bars.cut(host, recipe, slot)
    print(f"All {len(recipes)} original Metal Scaffolding recipes passed in survival.")


def run(args):
    with (ROOT / "fixtures/metal-scaffolding-java.csv").open(newline="") as stream:
        expected = list(csv.DictReader(stream))
    scenario = "MetalScaffoldingLan" if args.lan else "MetalScaffoldingSolo"
    env = {"HORIZON_NO_AUDIO": "1"}
    blocks = {}
    with ExitStack() as scope:
        host = scope.enter_context(fixture_world(args, scenario, pack=args.pack, env=env))
        actor, player = host, "@s"
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            player = "ScaffoldGuest"
            scratch = Path(scope.enter_context(TemporaryDirectory(prefix="hc-scaffold-")))
            actor = scope.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player,
                scenario="metal-scaffolding", pack=args.pack, env=env))
            mp.until("the guest to join", lambda: any(guest["name"] == player and guest["placed"]
                     for guest in host.call("lan", "status")["guests"]))
        host.commands((
            "/fill 6 176 18 16 181 26 minecraft:air",
            "/fill 6 175 18 16 175 26 minecraft:stone",
            f"/gamemode survival {player}",
        ))
        for index, material in enumerate(MATERIALS):
            x = 8 + 3 * index
            block = f"create:{material}_scaffolding"
            host.command(f"/tp {player} {x + .5} 176 24.5 180 35")
            if material == "copper":
                host.command(f"/setblock {x} 176 21 minecraft:water")
            host.command(f"/item replace entity {player} hotbar.0 with {block} 2")
            mp.until("the held scaffolding", lambda: mp.count(actor, block) == 2)
            actor.call("interact", x, 175, 21, "up")
            mp.until("the base scaffold to appear", lambda: actor.call("block", x, 176, 21)["block"] == block)
            actor.call("interact", x, 176, 21, "south")
            mp.until("the upper scaffold to appear", lambda: actor.call("block", x, 177, 21)["block"] == block)
            mp.until("consumption of both items", lambda: mp.count(actor, block) == 0)
            host.commands((
                f"/setblock {x} 179 21 {block} strict",
                f"/setblock {x} 175 21 minecraft:air",
            ))
            for phase, y in (("base", 176), ("upper", 177), ("free", 179)):
                blocks[f"{index}_{phase}"] = (x, y, 21)
        start = host.clock()
        actual = []
        for tick in range(5):
            if tick:
                host.step_to(start + tick)
            samples = [sample for sample in expected if int(sample["tick"]) == tick]
            for sample in samples:
                pos = blocks[sample["scenario"]]
                state = host.call("block", *pos)
                fields = {key: "-" for key in ("distance", "bottom", "waterlogged")}
                if "[" in state["state"]:
                    fields.update(pair.split("=", 1) for pair in state["state"].split("[")[1][:-1].split(","))
                actual.append({"tick": str(tick), "scenario": sample["scenario"], "block": state["block"], **fields})
                if args.lan:
                    mp.until("the guest to see the scaffold state", lambda:
                             actor.call("block", *pos)["state"] == state["state"])
        assert actual == expected, [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    print(f"{scenario} matched {len(expected)} Java metal scaffolding samples.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--lan", action="store_true")
    mode.add_argument("--stonecut", action="store_true")
    args = parser.parse_args()
    (stonecut if args.stonecut else run)(args)
