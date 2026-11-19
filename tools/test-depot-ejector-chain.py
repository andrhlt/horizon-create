#!/usr/bin/env python3
"""Compare two Weighted Ejectors handing the same ingot to a final Depot."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

launch = import_module("test-depot-ejector-launch")
track = import_module("test-track-crafting")
obstacle = import_module("test-depot-ejector-obstacle")
multiplayer = import_module("test-multiplayer")
SOURCE = "5 104 -11"
RECEIVER = "9 104 -11"
DEPOT = "13 104 -11"


def setup(host):
    host.commands((
        "/fill 2 103 -13 15 103 -9 minecraft:smooth_stone",
        "/fill 2 104 -13 15 112 -9 minecraft:air",
        f"/setblock {SOURCE} create:weighted_ejector[facing=east]{{HorizontalDistance:4,VerticalDistance:0}}",
        f"/setblock {RECEIVER} create:weighted_ejector[facing=east]{{HorizontalDistance:4,VerticalDistance:0}}",
        "/setblock 5 104 -12 create:creative_motor[facing=south]{ScrollValue:128}",
        f"/setblock {DEPOT} create:depot",
        "/gamemode spectator @s",
        "/tp @s 8.5 105 -9.5",
    ))


def observation(host, tick):
    first, a_items, a_flight, second, b_items, b_flight, b_pos, depot = host.commands((
        f"/data get block {SOURCE} State", f"/data get block {SOURCE} Items",
        f"/data get block {SOURCE} LaunchedItems",
        f"/data get block {RECEIVER} State", f"/data get block {RECEIVER} Items",
        f"/data get block {RECEIVER} LaunchedItems", f"/data get block {RECEIVER} BeltPosition",
        f"/data get block {DEPOT} Items",
    ))
    a = re.search(r"\b(CHARGED|LAUNCHING|RETRACTING)\b", first)
    b = re.search(r"\b(CHARGED|LAUNCHING|RETRACTING)\b", second)
    if a is None or b is None:
        raise RuntimeError(f"Missing chain Ejector state at tick {tick}: {first}, {second}")
    age_a = track.field(a_flight, "Time", -1.0)
    age_b = track.field(b_flight, "Time", -1.0)
    a_count, b_count = launch.count(a_items), launch.count(b_items)
    at = (launch.value(b_pos) or 0) if b_count else 0
    spilled = sum(item["item"]["count"] for item in obstacle.items_near(host, launch.ITEM))
    return (str(tick), a[1], str(a_count), str(int(age_a)), b[1], str(b_count), f"{at:.6f}",
            str(int(age_b)), str(launch.count(depot)), str(spilled))


def run(args):
    with args.reference.open() as source:
        data = csv.reader(source)
        header, expected = next(data), list(data)
    actual = []
    with ExitStack() as stack:
        world = "EjectorChainLAN" if args.multiplayer else "EjectorChain"
        host = stack.enter_context(fixture_world(args, world, pack=args.pack))
        setup(host)
        guest = None
        if args.multiplayer:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejector-chain-")))
            name = "EjectChainGuest"
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario="ejector-chain", pack=args.pack,
            ))
            multiplayer.until("the chain fixture guest joins", lambda: any(
                player["name"] == name and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((f"/gamemode survival {name}", f"/tp {name} 12.5 104 -9.5"))
            multiplayer.until("guest sees the final Depot", lambda:
                              guest.call("block", 13, 104, -11)["block"] == "create:depot")
        start = host.clock()
        for row in expected:
            tick = int(row[0])
            host.step_to(start + tick)
            if tick == 12:
                host.command(f'/data merge block {SOURCE} '
                             '{Items:[{Slot:0b,id:"minecraft:iron_ingot",count:1}],BeltPosition:0.5f}')
            actual.append(observation(host, tick))
            if tick == 24:
                host.command("/setblock 9 104 -12 create:creative_motor[facing=south]{ScrollValue:128}")
        if guest:
            guest.call("interact", 13, 104, -11, "up")
            multiplayer.until("guest collects the relayed ingot", lambda:
                              multiplayer.count(guest, launch.ITEM) == 1)
    if args.trace:
        with args.trace.open("w") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True)
                   if tuple(a[:6]) != b[:6] or tuple(a[7:]) != b[7:] or abs(float(a[6]) - float(b[6])) > .000002]
    if differences:
        raise RuntimeError(f"The Ejector chain differed on {len(differences)} Java ticks: {differences[:8]}")
    print(f"The charging handoff, two flights and Depot delivery matched all {len(actual)} Java ticks.")
    if args.multiplayer:
        print("The LAN guest collected the relayed ingot from the Depot.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/depot-ejector-chain-java.csv")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    run(parser.parse_args())
