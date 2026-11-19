#!/usr/bin/env python3
"""Replay an actual falling stack feeding a Weighted Ejector and its receiving Depot."""
import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

launch = import_module("test-depot-ejector-launch")
obstacle = import_module("test-depot-ejector-obstacle")
multiplayer = import_module("test-multiplayer")
EJECTOR = "5 104 -11"
DEPOT = "9 104 -11"
ITEM = '@e[type=minecraft:item,tag=EjectorInput,limit=1]'


def setup(host):
    host.commands((
        "/fill 3 103 -13 13 103 -9 minecraft:smooth_stone",
        "/fill 3 104 -13 13 112 -9 minecraft:air",
        f"/setblock {EJECTOR} create:weighted_ejector[facing=east]"
        "{HorizontalDistance:4,VerticalDistance:0,ScrollValue:3}",
        "/setblock 5 104 -12 create:creative_motor[facing=south]{ScrollValue:128}",
        f"/setblock {DEPOT} create:depot",
        "/gamemode spectator @s",
        "/tp @s 8.5 105 -9.5",
    ))


def capture(host, tick):
    state, held, flights, receiving, queued, loose = host.commands((
        f"/data get block {EJECTOR} State", f"/data get block {EJECTOR} Items",
        f"/data get block {EJECTOR} LaunchedItems", f"/data get block {DEPOT} Items",
        f"/data get block {EJECTOR} Incoming", f"/data get entity {ITEM}",
    ))
    actual_state = re.search(r"\b(CHARGED|LAUNCHING|RETRACTING)\b", state)
    if actual_state is None:
        raise RuntimeError(f"Missing Ejector state at tick {tick}: {state}")
    age = re.search(r"\bTime: (\d+)", flights)
    pending = re.findall(r"\bPos: (-?\d+(?:\.\d+)?)(?:f)?", queued)
    count = launch.count(loose)
    y, vy, grounded = 0.0, 0.0, "false"
    if count:
        pos, velocity = (obstacle.vector(loose, key) for key in ("Pos", "Motion"))
        ground = re.search(r"\bOnGround: (true|false|[01]b)", loose)
        if not pos or not velocity or not ground:
            raise RuntimeError(f"Cannot read in-world item at tick {tick}: {loose}")
        y, vy = pos[1] - 104.0, velocity[1]
        grounded = str(ground[1] in ("true", "1b")).lower()
    return (str(tick), actual_state[1], str(launch.count(held)), age[1] if age else "-1",
            str(launch.count(receiving)), str(len(pending)), f"{float(pending[0]) if pending else 0:.6f}",
            str(count), f"{y:.9f}", f"{vy:.9f}", grounded)


def run(args):
    with args.reference.open() as source:
        data = csv.reader(source)
        header, expected = next(data), list(data)
    actual = []
    with ExitStack() as stack:
        world = "EjectorDroppedLAN" if args.multiplayer else "EjectorDropped"
        host = stack.enter_context(fixture_world(args, world, pack=args.pack))
        setup(host)
        guest = None
        if args.multiplayer:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejector-dropped-")))
            name = "EjectorDropGuest"
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", name, scenario="ejector-dropped", pack=args.pack,
            ))
            multiplayer.until("the drop fixture guest joins", lambda: any(
                player["name"] == name and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((f"/gamemode survival {name}", f"/tp {name} 8.5 104 -9.5"))
            multiplayer.until("guest sees the receiving Depot", lambda:
                              guest.call("block", 9, 104, -11)["block"] == "create:depot")
        start = host.clock()
        obstacle.match_item_phase(host, 3)
        for row in expected:
            tick = int(row[0])
            host.step_to(start + tick)
            if tick == 12:
                host.command('/summon minecraft:item 5.5 106.5 -10.5 '
                             '{Item:{id:"minecraft:iron_ingot",count:3},'
                             'Motion:[0.0d,0.0d,0.0d],PickupDelay:32767s,Tags:["EjectorInput"]}')
            actual.append(capture(host, tick))
        if guest:
            guest.call("interact", 9, 104, -11, "up")
            multiplayer.until("guest collects the delivered stack", lambda:
                              multiplayer.count(guest, launch.ITEM) == 3)
    if args.trace:
        with args.trace.open("w") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True)
                   if tuple(a[:6]) != b[:6] or a[7] != b[7] or a[10] != b[10]
                   or any(abs(float(a[i]) - float(b[i])) > .000002 for i in (6, 8, 9))]
    if differences:
        raise RuntimeError(f"Dropped input differed on {len(differences)} Java ticks: {differences[:8]}")
    print(f"Dropped stack, Ejector launch and Depot delivery matched all {len(actual)} Java ticks.")
    if args.multiplayer:
        print("The LAN guest collected all three ingots from the Depot.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/depot-ejector-dropped-java.csv")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    run(parser.parse_args())
