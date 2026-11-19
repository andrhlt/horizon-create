#!/usr/bin/env python3
"""Replay the original loose-item collection and extraction flap of a horizontal Funnel."""
from argparse import ArgumentParser
from contextlib import ExitStack
import csv
from importlib import import_module
import json
from math import isclose
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
flap = import_module("test-ejector-funnel-flap")
GUEST = "FlapGuest"


def setup(host, extracting):
    inputs = (
        "/fill 2 103 -15 12 103 -8 minecraft:smooth_stone",
        "/fill 2 104 -15 12 110 -8 minecraft:air",
        "/setblock 5 106 -11 minecraft:redstone_block",
        "/setblock 5 104 -11 minecraft:smooth_stone",
        "/setblock 6 105 -11 minecraft:barrel",
        f"/setblock 5 105 -11 create:brass_funnel[facing=west,extracting={str(extracting).lower()}]",
        "/gamemode spectator @s",
        "/tp @s 6.5 106 -7.5",
    )
    host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in inputs))
    host.call("look-at", *flap.POSITION)


def main():
    parser = ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--extracting", action="store_true")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    os.environ["CREATE_FUNNEL_FLAP_RENDER"] = "1"
    os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    java_fixture = "plain-funnel-flap-java.csv"
    reference = args.reference or ROOT / "fixtures" / java_fixture
    with reference.open() as file:
        source = csv.reader(file)
        next(source)
        scenario = "extract" if args.extracting else "collect"
        original = {int(age): list(map(float, values)) for mode, age, *values in source if mode == scenario}
    for values in original.values():
        for segment, observed in enumerate(values[3:]):
            assert isclose(observed, flap.angle(values[1], segment), abs_tol=1e-5)
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "PlainFunnelFlap", render=True, pack=args.pack))
        setup(host, args.extracting)
        clients = {"host": host}
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejfl-")))
            guest = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST, render=True,
                scenario="plain-funnel-flap", pack=args.pack,
            ))
            mp.until("the viewing guest joins", lambda: any(
                player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            host.call("command", f"/gamemode spectator {GUEST}")
            host.call("command", f"/tp {GUEST} 6.5 106 -7.5")
            mp.until("the guest reaches the Funnel", lambda: guest.call("state")["player"]["position"] == flap.VIEW)
            guest.call("look-at", *flap.POSITION)
            clients["guest"] = guest
        start = host.clock()
        print(f"Original comparison begins at Horizon game tick {start}.", flush=True)
        for tick in range(1, 13):
            host.step_to(start + tick)
        logs = {role: game.socket.parent / "ctl.log" for role, game in clients.items()}
        offsets = {role: log.stat().st_size for role, log in logs.items()}
        if args.extracting:
            host.commands((
                '/data merge block 6 105 -11 {Items:[{Slot:0b,id:"minecraft:iron_ingot",count:1}]}',
                "/setblock 5 106 -11 minecraft:air",
            ))
        else:
            host.call("command", "/setblock 5 106 -11 minecraft:air")
            host.call("command", '/summon minecraft:item 5.4 105.12 -10.5 '
                      '{Item:{id:"minecraft:iron_ingot",count:1},NoGravity:1b,PickupDelay:32767s}')
        first_frame = 14
        for tick in range(13, first_frame + len(original)):
            host.step_to(start + tick)
            age = tick - first_frame
            if age in original:
                for role, log in logs.items():
                    def rendered():
                        row = flap.poses(log, offsets[role]).get(age)
                        return row is not None and row[0] == start + tick

                    mp.until(f"{role} renders Funnel flap age {age} at game tick {start + tick}", rendered)
        inventory = host.command("/data get block 6 105 -11 Items")
        assert ("minecraft:iron_ingot" in inventory) != args.extracting, inventory
        for peer in clients.values():
            def iron_drops():
                return sum(entry["item"]["count"] for entry in peer.call("entities", 16, "minecraft:item")["entities"]
                           if entry["item"]["item"] == "minecraft:iron_ingot")

            mp.until("actual loose iron count", lambda: iron_drops() == int(args.extracting))
        for role, log in logs.items():
            rows = flap.poses(log, offsets[role])
            if args.trace:
                args.trace.with_suffix(f".{role}.log").write_text(flap.wrench.read_since(log, offsets[role]))
            actual = flap.cue_logs(log, offsets[role])
            assert actual == flap.SOUNDS, (role, actual, sorted(rows))
            observed = flap.verify(rows, original, role)
            print(f"{role} matched {observed} original four-segment flap samples and {len(actual)} layered playbacks.")


if __name__ == "__main__":
    main()
