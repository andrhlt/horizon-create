#!/usr/bin/env python3
"""Replay ordinary crouch clicks while holding a Weighted Ejector."""
from argparse import ArgumentParser
import csv
from contextlib import ExitStack
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
EJECTOR = "create:weighted_ejector"
STONE = "minecraft:smooth_stone"
GUEST = "EjectClickGuest"
MARK = (9, 104, -11)
EMPTY = (9, 104, -9)
OTHER = (9, 104, -13)
BASE = (5, 103, -11)


def click(host, actor, pos, place=False):
    x, y, z = pos
    actor.call("look-at", x + .5, y + .5, z + .5)
    actor.call("key", "shift", "down")
    host.step_to(host.clock() + 1)
    try:
        if place:
            actor.call("interact", *pos, "up")
            actor.call("wait", 4)
        else:
            actor.call("mouse", "left", "click")
            host.step_to(host.clock() + 1)
    finally:
        actor.call("key", "shift", "up")
    actor.call("wait", 4)
    host.step_to(host.clock() + 1)


def xyz(pos):
    return " ".join(map(str, pos))


def main():
    parser = ArgumentParser()
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/weighted-ejector-target-click-java.csv")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with args.reference.open() as source:
        expected = {row["case"]: row["canceled"] == "true" for row in csv.DictReader(source)}
    with ExitStack() as stack:
        suffix = "LAN" if args.lan else "Solo"
        host = stack.enter_context(fixture_world(args, f"EjectorTargetClick{suffix}", render=True, pack=args.pack))
        actor, name = host, "@s"
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-eject-click-")))
            actor = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST, render=True, scenario=f"eject-click-{suffix}", pack=args.pack))
            name = GUEST
            multiplayer.until("guest joined", lambda: any(
                p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]))
        setup = (
            "/fill 3 103 -15 14 103 -8 minecraft:smooth_stone",
            "/fill 3 104 -15 14 109 -8 minecraft:air",
            *(f"/setblock {xyz(pos)} {STONE}" for pos in (MARK, EMPTY, OTHER)),
            f"/gamemode creative {name}",
            f"/give {name} {EJECTOR}",
            f"/tp {name} 11.5 104 -10.5",
        )
        host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in setup))
        multiplayer.until("the player holds a Weighted Ejector", lambda: multiplayer.count(actor, EJECTOR) == 1)
        multiplayer.until("the target area is loaded", lambda: actor.call("block", *MARK)["block"] == STONE)
        actor.call("select", EJECTOR)

        click(host, actor, EMPTY)
        broke_before_mark = host.call("block", *EMPTY)["block"] == "minecraft:air"
        click(host, actor, MARK, place=True)
        mark_consumed = host.call("block", MARK[0], MARK[1] + 1, MARK[2])["block"] == "minecraft:air"
        click(host, actor, OTHER)
        broke_after_mark = host.call("block", *OTHER)["block"] == "minecraft:air"
        still_marked = host.call("block", *MARK)["block"] == STONE

        host.command(f"/tp {name} 5.5 104 -12.5")
        host.step_to(host.clock() + 1)
        actor.call("look-at", 5.5, 105.62, -8.5)
        actor.call("interact", *BASE, "up")
        multiplayer.until("creative placed Ejector", lambda: host.call("block", 5, 104, -11)["block"] == EJECTOR)
        block = host.call("block", 5, 104, -11)
        distance = host.command("/data get block 5 104 -11 HorizontalDistance")
        if not still_marked or "facing=east" not in block["state"] or not distance.endswith(" 4"):
            raise RuntimeError(f"Unrelated click changed the target placement: {block['state']}, {distance}.")

        host.command(f"/tp {name} 11.5 104 -10.5")
        host.step_to(host.clock() + 1)
        multiplayer.until("player returns to the near side of the target", lambda:
                          actor.call("state")["player"]["position"] == [11.5, 104, -10.5])
        click(host, actor, MARK, place=True)
        multiplayer.until("the second target selection is acknowledged", lambda:
                          actor.call("messages")["actionbar"] == "Target Selected")
        click(host, actor, MARK)
        actual = {
            "without_selection": not broke_before_mark,
            "mark": mark_consumed,
            "other": not broke_after_mark,
            "selected": host.call("block", *MARK)["block"] == STONE,
        }
        if actual != expected:
            raise RuntimeError(f"Java click cancellation {expected}, Horizon {actual}.")
        print("Crouch-left-click broke both unrelated blocks and preserved the marked target.")
        print("The marked block itself survived deselection, matching Java.")


if __name__ == "__main__":
    main()
