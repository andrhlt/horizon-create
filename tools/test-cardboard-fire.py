#!/usr/bin/env python3
"""Compare the Cardboard Block's original flint-and-steel interaction."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")


def ignite(world, actor, name, row, z):
    tool = "minecraft:flint_and_steel"
    position = (11.5, 109, z + 0.5)
    world.commands((
        f"/setblock 8 110 {z} {row['support']}",
        f"/item replace entity {name} weapon.mainhand with {tool}",
        f"/tp {name} {' '.join(map(str, position))} 90 14",
    ))
    mp.until("the operator to reach the fire test", lambda:
             tuple(actor.call("state")["player"]["position"]) == position)
    mp.until("the operator to hold flint and steel", lambda:
             (actor.call("inventory")["held"] or {}).get("item") == tool)
    actor.call("look-at", 8.98, 110.5, z + 0.5)
    target = actor.call("looking-at")
    assert target["kind"] == "block" and target["block"]["pos"] == [8, 110, z], target
    assert target["block"]["face"] == "east", target
    actor.call("mouse", "right", "click")
    actor.call("wait", 6)

    state = world.call("block", 9, 110, z)["block"]
    damage = world.command(f'/data get entity {name} SelectedItem.components."minecraft:damage"')
    value = re.search(r"entity data: (\d+)", damage)
    actual = (state, int(value[1]) if value else 0)
    assert actual == (row["adjacent"], int(row["tool_damage"])), (row, actual, damage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/cardboard-fire-java.csv").open() as reference:
        rows = list(csv.DictReader(reference))
    with ExitStack() as stack:
        scenario = "CardboardFireGuest" if args.lan else "CardboardFire"
        world = stack.enter_context(fixture_world(args, scenario, render=True, pack=args.pack))
        world.commands((
            "/fill 4 107 -18 16 114 -4 minecraft:air",
            "/fill 11 108 -16 14 108 -6 minecraft:stone",
        ))
        actor, name = world, "@s"
        if args.lan:
            world.command("/tp @s 14.5 109 -15.5")
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-cardboard-fire-")))
            name = "CardFireGuest"
            actor = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", name,
                render=True, scenario="cardboard-fire", pack=args.pack,
            ))
            mp.until("the fire test guest to join", lambda: any(
                guest["name"] == name and guest["placed"] for guest in world.call("lan", "status")["guests"]
            ))
        world.command(f"/gamemode survival {name}")
        for row, z in zip(rows, (-12, -8), strict=True):
            ignite(world, actor, name, row, z)
    print(f"Matched {len(rows)} original Java Cardboard and stone flint-and-steel cases.")


if __name__ == "__main__":
    main()
