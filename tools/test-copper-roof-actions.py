#!/usr/bin/env python3
"""Replay Java waxing, stripping, and scraping of Create Copper Roofs."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
stone = import_module("test-stone-palettes")
POS = (8, 100, 21)
POSITION = (8.5, 100, 24.5)
AT = " ".join(map(str, POS))


def normalized(value):
    return value.split("[", 1)[0], stone.state_properties(value)


def act(world, actor, name, state, tool):
    world.commands((
        f"/setblock {AT} minecraft:air",
        f"/setblock {AT} {state}",
        f"/item replace entity {name} weapon.mainhand with {tool}",
    ))
    expected_tool = tool.split("[", 1)[0].split()[0]
    mp.until(f"the player to hold {expected_tool}", lambda:
             (actor.call("inventory")["held"] or {}).get("item") == expected_tool)
    mp.until("the initial roof state to reach the player", lambda:
             normalized(actor.call("block", *POS)["state"]) == normalized(state))
    actor.call("look-at", 8.5, 100.25, 21.9)
    hit = actor.call("looking-at")
    assert hit["kind"] == "block" and tuple(hit["block"]["pos"]) == POS, hit
    actor.call("mouse", "right", "click")
    actor.call("wait", 4)
    result = world.call("block", *POS)["state"]
    count = mp.count(actor, "minecraft:honeycomb")
    reply = world.command(f'/data get entity {name} SelectedItem.components."minecraft:damage"')
    damage = re.search(r"entity data: (\d+)", reply)
    return result, count, int(damage[1]) if damage else 0


def main():
    parser = argparse.ArgumentParser()
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/copper-roof-actions-java.csv").open(newline="") as source:
        reference = list(csv.DictReader(source, delimiter=";"))
    differences = []
    with ExitStack() as stack:
        scenario = "CopperRoofActionsLAN" if args.lan else "CopperRoofActions"
        world = stack.enter_context(fixture_world(args, scenario, render=True, pack=args.pack))
        world.commands(("/fill 5 99 18 14 99 26 minecraft:smooth_stone", "/tp @s 8.5 100 24.5"))
        actor, name = world, "@s"
        if args.lan:
            world.command("/tp @s 13.5 100 25.5")
            name = "RoofWaxGuest"
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            folder = Path(stack.enter_context(TemporaryDirectory(prefix="hc-roof-wax-")))
            actor = stack.enter_context(mp.joined_client(
                args, folder, f"127.0.0.1:{port}", name,
                render=True, scenario="copper-roof-actions", pack=args.pack,
            ))
            mp.until("guest to join", lambda: any(
                guest["name"] == name and guest["placed"] for guest in world.call("lan", "status")["guests"]
            ))
            world.command(f"/tp {name} 8.5 100 24.5 180 25")
            mp.until("guest to reach the Copper Roof", lambda:
                     tuple(actor.call("state")["player"]["position"]) == POSITION)
        world.command(f"/gamemode survival {name}")
        for row in reference:
            for action, before, after, tool, remaining in (
                ("wax", "initial", "waxed", "minecraft:honeycomb 2", "honeycomb"),
                ("strip", "waxed", "stripped", "minecraft:iron_axe", "strip_damage"),
                ("scrape", "stripped", "scraped", "minecraft:iron_axe[minecraft:damage=1]", "scrape_damage"),
            ):
                actual_state, honeycomb, durability = act(world, actor, name, row[before], tool)
                actual_item = honeycomb if action == "wax" else durability
                if (normalized(actual_state), actual_item) != (normalized(row[after]), int(row[remaining])):
                    differences.append((action, row[before], row[after], actual_state, row[remaining], actual_item))
    print(f"Compared {3 * len(reference)} original Copper Roof actions, {len(differences)} differences.", flush=True)
    for difference in differences[:9]:
        print(difference, flush=True)
    raise SystemExit(bool(differences))


if __name__ == "__main__":
    main()
