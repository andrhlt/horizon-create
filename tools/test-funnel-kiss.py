#!/usr/bin/env python3
"""Compare the hidden Funnel Kiss award on the original Wrench action."""
from argparse import ArgumentParser
from contextlib import ExitStack
import csv
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

adv = import_module("test-first-advancements")
mp = adv.multiplayer
GUEST = "FunnelKiss"
WRENCH = "create:wrench"
AWARD = ("belt_funnel_kiss",)


def setup(host):
    all_rigs = []
    for case in range(4):
        z = -11 + case * 4
        rig = [
            f"/fill 3 103 {z-3} 7 103 {z+1} minecraft:smooth_stone",
            f"/fill 3 104 {z-3} 7 110 {z+1} minecraft:air",
            f"/setblock 5 104 {z} create:belt[facing=east,part=middle,slope=horizontal]",
            f"/setblock 4 104 {z} create:belt[facing=east,part=middle,slope=horizontal]",
            f"/setblock 5 105 {z} create:brass_belt_funnel[facing=west,shape=retracted]",
        ]
        if case:
            facing = "west" if case == 1 else "east"
            shape = "retracted" if case == 2 else "extended"
            rig.append(f"/setblock 4 105 {z} create:brass_belt_funnel[facing={facing},shape={shape}]")
        all_rigs.extend(rig)
    host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in all_rigs))


def state(control, z):
    return control.call("block", 5, 105, z)["state"].split("shape=")[1].split(",")[0].strip("]")


def click(host, actor, name, observer, case):
    z = -11 + case * 4
    position = [5.5, 104, z - 1.5]
    host.command(f"/tp {name} {position[0]} {position[1]} {position[2]}")
    host.step_to(host.clock() + 1)
    mp.until("the player reaches the north side of the Funnel", lambda:
             actor.call("state")["player"]["position"] == position)
    actor.call("select", WRENCH)
    actor.call("look-at", 5.5, 105.45, z + .5)
    assert state(host, z) == "retracted"
    before, = adv.progress(host, name, AWARD)
    started = host.clock()
    actor.call("interact", 5, 105, z, "north")
    mp.until("the Wrench expands the Belt Funnel", lambda: state(host, z) == "extended")
    assert host.clock() == started, "The Wrench action should leave the fixture clock frozen."
    mode = state(host, z)
    after, = adv.progress(host, name, AWARD)
    other = "false" if observer is None else adv.progress(host, observer, AWARD)[0]
    mp.until("the actor sees the authoritative Funnel shape", lambda: state(actor, z) == mode)
    return [str(case), mode, before, after, other, str(mp.count(actor, WRENCH))]


def main():
    parser = ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/funnel-kiss-java.csv")
    parser.add_argument("--guest-owner", action="store_true")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with args.reference.open() as source:
        rows = csv.reader(source)
        next(rows)
        expected = list(rows)
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "FunnelKiss", render=True, pack=args.pack))
        actor, name, observer = host, "@s", None
        if args.lan or args.guest_owner:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-fkiss-")))
            guest = stack.enter_context(mp.joined_client(args, scratch, f"127.0.0.1:{port}", GUEST,
                                                       render=True, scenario="funnel-kiss", pack=args.pack))
            mp.until("the multiplayer observer finishes joining", lambda: any(
                player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            observer = GUEST
            if args.guest_owner:
                actor, name, observer = guest, GUEST, "@s"
        setup(host)
        host.command(f"/gamemode survival {name}")
        host.command(f"/give {name} {WRENCH}")
        mp.until("the operating player's Wrench", lambda: mp.count(actor, WRENCH) == 1)
        actual = [click(host, actor, name, observer, case) for case in range(len(expected))]
    for row in actual:
        print(",".join(row))
    assert actual == expected, f"Java {expected}, Horizon {actual}"
    print(f"Matched all {len(actual)} original Funnel Kiss action ticks and ownership controls.")


if __name__ == "__main__":
    main()
