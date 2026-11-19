#!/usr/bin/env python3
"""Replay the original Wrench changes for normal and Belt Funnels."""
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
WRENCH = "create:wrench"
GUEST = "FunnelWrench"
INITIAL = ("false", "true", "pulling", "pushing", "extended", "retracted", "retracted")


def setup(host, name):
    commands = [f"/gamemode survival {name}"]
    for i, variant in enumerate(INITIAL):
        z = -11 + i * 3
        support = "create:depot"
        if i >= 4:
            support = f"create:belt[facing=east,part=middle,slope={'upward' if i == 6 else 'horizontal'}]"
        funnel = (f"create:brass_funnel[facing=west,extracting={variant}]" if i < 2 else
                  f"create:brass_belt_funnel[facing=west,shape={variant}]")
        commands.extend((
            f"/fill 3 103 {z-1} 7 103 {z+1} minecraft:smooth_stone",
            f"/fill 3 104 {z-1} 7 110 {z+1} minecraft:air",
            f"/setblock 5 104 {z} {support}",
            f"/setblock 6 105 {z} minecraft:barrel",
            # The Java GameTest installs the exact starting block state directly.
            f"/setblock 5 105 {z} {funnel} strict",
        ))
    host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in commands))


def mode(actor, z):
    return re.search(r"\b(?:shape|extracting)=(\w+)", actor.call("block", 5, 105, z)["state"])[1]


def wrench(host, actor, name, case):
    z = -11 + case * 3
    preparation=(f"/clear {name} {WRENCH}",f"/give {name} {WRENCH}",f"/tp {name} 3.5 104 {z + .5}")
    host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in preparation))
    host.step_to(host.clock() + 1)
    mp.until("player reaches the Funnel", lambda:
             actor.call("state")["player"]["position"] == [3.5, 104, z + .5])
    mp.until("the player holds the Wrench", lambda: mp.count(actor, WRENCH) == 1)
    actor.call("select", WRENCH)
    actor.call("look-at", 5.5, 105.45, z + .5)
    assert mode(host, z) == INITIAL[case]
    actor.call("interact", 5, 105, z, "west")
    host.step_to(host.clock() + 1)
    actual = mode(host, z)
    mp.until("the client sees the authoritative Funnel mode", lambda: mode(actor, z) == actual)
    return [str(case), actual, str(mp.count(actor, WRENCH))]


def main():
    parser = ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/funnel-wrench-modes-java.csv")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with args.reference.open() as source:
        rows = csv.reader(source)
        next(rows)
        expected = list(rows)
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "FunnelWrenchModes", render=True, pack=args.pack))
        actor, name = host, "@s"
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-flpc-")))
            actor = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST, render=True, scenario="funnel-wrench-modes", pack=args.pack,
            ))
            name = GUEST
            mp.until("the guest can use the Wrench", lambda: any(
                p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]
            ))
        setup(host, name)
        actual = [wrench(host, actor, name, case) for case in range(len(expected))]
    for row in actual:
        print(",".join(row))
    assert actual == expected, f"Java {expected}, Horizon {actual}"
    print(f"Matched all {len(actual)} real Funnel Wrench mode cases.")


if __name__ == "__main__":
    main()
