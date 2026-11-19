#!/usr/bin/env python3
"""Replay the original inward flap as a moving Belt feeds a Funnel."""
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
CONNECTOR = "create:belt_connector"
GUEST = "FlapGuest"


def setup(host):
    preparation = (
        "/fill 1 103 -15 12 103 -8 minecraft:smooth_stone",
        "/fill 1 104 -15 12 110 -8 minecraft:air",
        "/setblock 2 104 -11 create:shaft[axis=z]",
        "/setblock 6 104 -11 create:shaft[axis=z]",
        "/gamemode creative @s",
        f"/give @s {CONNECTOR}",
        "/tp @s 4 104 -7.5",
    )
    host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in preparation))
    host.call("select", CONNECTOR)
    mp.until("the belt connector is equipped", lambda:
             CONNECTOR in host.command("/data get entity @s SelectedItem"))
    host.call("interact", 2, 104, -11)
    mp.until("first shaft is selected", lambda:
             "CreateBeltFirstShaft" in host.command("/data get entity @s SelectedItem"))
    for _ in range(5):
        host.step_to(host.clock() + 1)
    host.call("interact", 6, 104, -11)
    mp.until("the physical connector creates a belt", lambda:
             host.call("block", 5, 104, -11)["block"] == "create:belt")
    inputs = (
        "/setblock 2 104 -12 create:creative_motor[facing=south]{ScrollValue:-48}",
        "/setblock 6 105 -11 minecraft:barrel",
        "/setblock 5 105 -11 create:brass_belt_funnel[facing=west,shape=retracted]",
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
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    os.environ["CREATE_FUNNEL_FLAP_RENDER"] = "1"
    os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    java_fixture = "belt-funnel-moving-flap-java.csv"
    reference = args.reference or ROOT / "fixtures" / java_fixture
    with reference.open() as file:
        source = csv.reader(file)
        next(source)
        original = {int(age): list(map(float, values)) for age, *values in source}
    for values in original.values():
        for segment, observed in enumerate(values[3:]):
            assert isclose(observed, flap.angle(values[1], segment), abs_tol=1e-5)
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "MovingBeltFunnelFlap", render=True, pack=args.pack))
        setup(host)
        clients = {"host": host}
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejfl-")))
            guest = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST, render=True,
                scenario="moving-belt-funnel-flap", pack=args.pack,
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
        host.command('/data merge block 2 104 -11 {Inventory:{PositiveOrder:1b,Items:['
                     '{Item:{id:"minecraft:iron_ingot",count:1},PrevPos:0.4375f,Pos:0.4375f,Angle:180}]}}')
        delivered = None
        for tick in range(13, 120):
            host.step_to(start + tick)
            if "minecraft:iron_ingot" in host.command("/data get block 6 105 -11 Items"):
                delivered = start + tick
                break
        assert delivered is not None, "The Belt must actually send the item through the Funnel to the barrel."
        for age in range(len(original)):
            host.step_to(delivered + age + 1)
            for role, log in logs.items():
                def rendered():
                    row = flap.poses(log, offsets[role]).get(age)
                    return row is not None and row[0] == delivered + age + 1

                mp.until(f"{role} renders flap age {age} after the Belt transfer", rendered)
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
