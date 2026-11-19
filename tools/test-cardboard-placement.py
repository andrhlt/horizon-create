#!/usr/bin/env python3
"""Trace original Cardboard Block placement against the playable Horizon pack."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

FLOOR = (8, 104, -12)
DESTINATION = (8, 105, -12)
POSITIONS = {"180": (8.5, 105, -9.5), "90": (11.5, 105, -11.5)}
ITEM = "create:cardboard_block"
mp = import_module("test-multiplayer")


def place(world, actor, name, original, *, item=ITEM, prepare=True):
    if prepare:
        world.commands((
            "/fill 4 104 -17 14 104 -7 minecraft:smooth_stone",
            "/fill 4 105 -17 14 109 -7 minecraft:air",
            f"/gamemode survival {name}",
        ))
    differences = []
    for row in original:
        world.commands((
            "/setblock 8 105 -12 minecraft:air",
            f"/item replace entity {name} weapon.mainhand with {item}",
        ))
        position = POSITIONS[row["yaw"]]
        pitch = {"180": 39, "90": 29}[row["yaw"]]
        world.command(f"/tp {name} {' '.join(map(str, position))} {row['yaw']} {pitch}")
        mp.until("the operator to reach the placement position", lambda:
                 tuple(actor.call("state")["player"]["position"]) == position)
        mp.until(f"the operator to hold {item}", lambda:
                 (actor.call("inventory")["held"] or {}).get("item") == item)
        actor.call("look-at", 8.5, 104.98, -11.5)
        target = actor.call("looking-at")
        assert target["kind"] == "block" and target["block"]["pos"] == list(FLOOR), target
        actor.call("mouse", "right", "click")
        mp.until("the placed block to reach the server", lambda:
                 world.call("block", *DESTINATION)["block"] == item)
        mp.until(f"the operator to consume {item}", lambda:
                 actor.call("inventory")["counts"].get(item, 0) == int(row["held"]))
        state = world.call("block", *DESTINATION)["state"]
        count = actor.call("inventory")["counts"].get(item, 0)
        expected_state = f'{item}[axis={row["axis"]}]'
        if (state, count) != (expected_state, int(row["held"])):
            differences.append((row["yaw"], expected_state, state, row["held"], count))
    if differences:
        raise AssertionError(differences)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/cardboard-placement-java.csv")
    args = parser.parse_args()
    with args.reference.open(newline="") as reference:
        original = list(csv.DictReader(reference))
    with ExitStack() as stack:
        scenario = "CardboardPlacementGuest" if args.lan else "CardboardPlacement"
        world = stack.enter_context(fixture_world(args, scenario, render=True, pack=args.pack))
        actor, name = world, "@s"
        if args.lan:
            world.command("/tp @s 14.5 105 -16.5")
            name = "CardboardGuest"
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            directory = Path(stack.enter_context(TemporaryDirectory(prefix="hc-cardboard-")))
            actor = stack.enter_context(mp.joined_client(
                args, directory, f"127.0.0.1:{port}", name,
                render=True, scenario="cardboard-placement", pack=args.pack,
            ))
            mp.until("the placement guest to join", lambda: any(
                guest["name"] == name and guest["placed"] for guest in world.call("lan", "status")["guests"]
            ))
        place(world, actor, name, original)
    print(f"Matched {len(original)} Java Cardboard Block placement actions.")


if __name__ == "__main__":
    main()
