#!/usr/bin/env python3
"""Replay Java crouching descent through each metal scaffolding column."""

import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
Y = 176


def compare(actor, player, host, x, material, expected):
    block = f"create:{material}_scaffolding"
    host.commands((
        f"/setblock {x} 170 21 minecraft:stone",
        f"/fill {x} 171 21 {x} 175 21 {block}[bottom=false,distance=0] strict",
        f"/tp {player} {x + .5} {Y} 21.5",
    ))
    mp.until("the stack and player position to sync", lambda:
             actor.call("block", x, 175, 21)["block"] == block
             and actor.call("state")["player"]["position"] == [x + .5, Y, 21.5])
    actor.call("wait", 5)
    replies = actor.call("script", script="state\nkey shift down\n" +
                         "wait 1\nstate\n" * (len(expected) - 1) + "key shift up\n")
    samples = [reply for reply in replies if "player" in reply]
    first = samples[0]["ticks"]
    for row, sample in zip(expected, samples, strict=True):
        state = sample["player"]
        dy = state["position"][1] - Y
        vy = state["velocity"][1]
        assert int(row["tick"]) == sample["ticks"] - first, (row, sample)
        assert abs(dy - float(row["dy"])) < 1e-7 and abs(vy - float(row["vy"])) < 1e-7, (row, dy, vy)


def run(args):
    with (ROOT / "fixtures/metal-scaffolding-descent-java.csv").open(newline="") as stream:
        expected = list(csv.DictReader(stream))
    scenario = "ScaffoldDescentLan" if args.lan else "ScaffoldDescentSolo"
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as scope:
        host = scope.enter_context(fixture_world(args, scenario, render=True, pack=args.pack, env=env))
        actor, player = host, "@s"
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            player = "DescentGuest"
            scratch = Path(scope.enter_context(TemporaryDirectory(prefix="hc-descent-")))
            actor = scope.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", player, render=True,
                scenario=scenario, pack=args.pack, env=env))
            mp.until("the guest to join", lambda: any(guest["name"] == player and guest["placed"]
                     for guest in host.call("lan", "status")["guests"]))
        host.command(f"/gamemode survival {player}")
        for index, material in enumerate(dict.fromkeys(row["material"] for row in expected)):
            compare(actor, player, host, 8 + 3 * index, material,
                    [row for row in expected if row["material"] == material])
    print(f"{scenario} matched {len(expected)} Java crouching descent samples.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())
