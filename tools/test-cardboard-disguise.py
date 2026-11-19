#!/usr/bin/env python3
"""Replay Java Cardboard disguise body and visibility states."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
JAVA_PHASE_TICKS = (0, 5, 9, 14, 19, 24)


def main():
    parser = argparse.ArgumentParser(description="Replay the original Cardboard disguise phases")
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/cardboard-disguise-java.csv").open(newline="") as source:
        reference = {int(row["tick"]): row for row in csv.DictReader(source)}
    with ExitStack() as stack:
        scenario = "CardboardDisguiseLAN" if args.lan else "CardboardDisguise"
        world = stack.enter_context(fixture_world(args, scenario, render=True, pack=args.pack))
        world.commands(("/fill 4 169 18 15 169 29 minecraft:stone", "/tp @s 8.5 170 23.5"))
        actor, player = world, "@s"
        if args.lan:
            world.command("/tp @s 10.5 170 26.5")
            player = "BoxGuest"
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            folder = Path(stack.enter_context(TemporaryDirectory(prefix="hc-box-")))
            actor = stack.enter_context(mp.joined_client(
                args, folder, f"127.0.0.1:{port}", player,
                render=True, scenario="cardboard-disguise", pack=args.pack,
            ))
            mp.until("the disguise guest to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in world.call("lan", "status")["guests"]
            ))
            world.command(f"/tp {player} 8.5 170 23.5")
            mp.until("the disguise guest to reach the floor", lambda:
                     tuple(actor.call("state")["player"]["position"]) == (8.5, 170, 23.5))
        world.commands((
            f"/gamemode survival {player}",
            f"/item replace entity {player} armor.head with create:cardboard_helmet",
            f"/item replace entity {player} armor.chest with create:cardboard_chestplate",
            f"/item replace entity {player} armor.legs with create:cardboard_leggings",
        ))
        boots = f"/item replace entity {player} armor.feet with "
        actions = (
            None, lambda: actor.call("key", "shift", "down"),
            lambda: world.command(boots + "create:cardboard_boots"),
            lambda: world.command(boots + "minecraft:air"),
            lambda: world.command(boots + "create:cardboard_boots"),
            lambda: actor.call("key", "shift", "up"),
        )
        for tick, action in zip(JAVA_PHASE_TICKS, actions, strict=True):
            if action:
                action()
            actor.call("wait", 5)
            p = actor.call("state")["player"]
            eye = round(p["eye"][1] - p["position"][1], 4)
            observed = (p["pose"], round(p["body_width"], 4), round(p["body_height"], 4), eye,
                        round(p["visibility"], 4), p["cardboard_disguised"])
            row = reference[tick]
            expected = (row["pose"], float(row["width"]), float(row["height"]), float(row["eye_height"]),
                        float(row["visibility"]), row["disguised"] == "true")
            if observed != expected:
                raise AssertionError((tick, expected, observed))
            if args.lan:
                def host_body_matches():
                    guest = next(g for g in world.call("lan", "status")["guests"] if g["name"] == player)
                    return (guest["pose"], round(guest["body_width"], 4), round(guest["body_height"], 4),
                            round(guest["eye_height"], 4), guest["cardboard_disguised"]) == (*expected[:4], expected[-1])
                mp.until(f"the host to observe the disguise body in phase {tick}", host_body_matches)
    print(f"All {len(JAVA_PHASE_TICKS)} stable Java Cardboard disguise states matched.", flush=True)


if __name__ == "__main__":
    main()
