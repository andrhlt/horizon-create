#!/usr/bin/env python3
"""Place Brass Funnels through a barrel side face above stationary supports."""
from argparse import ArgumentParser
from contextlib import ExitStack
import csv
from importlib import import_module
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
FUNNEL = "create:brass_funnel"
VARIANTS = {FUNNEL, "create:brass_belt_funnel"}
SUPPORTS = ("minecraft:smooth_stone", "create:depot", "create:weighted_ejector")
GUEST = "PlaceFunnelGuest"


def setup(host, name):
    commands = [f"/gamemode survival {name}"]
    for i in range(6):
        z = -11 + i * 3
        commands.extend((
            f"/fill 3 103 {z-1} 7 103 {z+1} minecraft:smooth_stone",
            f"/fill 3 104 {z-1} 7 110 {z+1} minecraft:air",
            f"/setblock 5 104 {z} {SUPPORTS[i // 2]}",
            f"/setblock 6 105 {z} minecraft:barrel",
        ))
    host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in commands))


def pose(actor, z):
    info = actor.call("block", 5, 105, z)
    block = info["block"]
    if block not in VARIANTS:
        return block, "", ""
    state = info["state"]
    direction = re.search(r"\bfacing=(\w+)", state)[1]
    variant = re.search(r"\b(?:shape|extracting)=(\w+)", state)[1]
    return block, direction, variant


def place(host, actor, name, case):
    z = -11 + case * 3
    shortcuts = (
        f"/clear {name} {FUNNEL}", f"/give {name} {FUNNEL}", f"/tp {name} 3.5 104 {z + .5}",
    )
    host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in shortcuts))
    host.step_to(host.clock() + 1)
    mp.until("the player is beside the barrel", lambda:
             actor.call("state")["player"]["position"] == [3.5, 104, z + .5])
    mp.until("the player holds exactly one Funnel", lambda: mp.count(actor, FUNNEL) == 1)
    actor.call("select", FUNNEL)
    actor.call("look-at", 6, 105.5, z + .5)
    if case % 2:
        actor.call("key", "shift", "down")
    host.step_to(host.clock() + 1)
    try:
        actor.call("interact", 6, 105, z, "west")
        host.step_to(host.clock() + 1)
        actor.call("wait", 4)
    finally:
        if case % 2:
            actor.call("key", "shift", "up")
    block, facing, variant = pose(host, z)
    if block in VARIANTS:
        mp.until("the client sees the placed Funnel", lambda: pose(actor, z) == (block, facing, variant))
        mp.until("actual placement consumed the held Funnel", lambda: mp.count(actor, FUNNEL) == 0)
    else:
        actor.call("close")
    return [str(case), block, facing, variant, str(mp.count(actor, FUNNEL))]


def main():
    parser = ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/stationary-funnel-placement-java.csv")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with args.reference.open() as source:
        rows = csv.reader(source)
        next(rows)
        expected = list(rows)
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "StationaryFunnelPlacement", render=True, pack=args.pack))
        actor, name = host, "@s"
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-flpc-")))
            actor = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST, render=True, scenario="stationary-funnel", pack=args.pack,
            ))
            name = GUEST
            mp.until("the guest can place the Funnel", lambda: any(
                p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]
            ))
        setup(host, name)
        actual = [place(host, actor, name, case) for case in range(len(expected))]
    for row in actual:
        print(",".join(row))
    assert actual == expected, f"Java {expected}, Horizon {actual}"
    print(f"Matched all {len(actual)} real Funnel placements and item consumption.")


if __name__ == "__main__":
    main()
