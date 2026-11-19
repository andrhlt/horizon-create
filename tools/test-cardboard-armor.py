#!/usr/bin/env python3
"""Craft and equip the original Cardboard armor in Horizon survival."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
crafting = import_module("test-survival-crafting")
SLOTS = {"helmet": "head", "chestplate": "chest", "leggings": "legs", "boots": "feet"}


def replay(world, actor, player, reference):
    pattern = reference["pattern"].split("/")
    cells = tuple(100 + row * 3 + column for row, line in enumerate(pattern)
                  for column, cell in enumerate(line) if cell == "P")
    item = reference["name"]
    world.commands((
        f"/clear {player}",
        f"/item replace entity {player} hotbar.0 with create:cardboard {len(cells)}",
    ))
    mp.until("the crafter to receive the Cardboard", lambda:
             mp.count(actor, "create:cardboard") == int(reference["ingredients"]))
    actor.call("interact", 12, 170, 24, "up")
    crafting.distribute(actor, 0, cells)
    crafting.output(actor, item, int(reference["count"]))
    actor.call("click-slot", 200, "shift")
    mp.until("the crafter to receive the new armor", lambda: mp.count(actor, item) == int(reference["count"]))
    if mp.count(actor, "create:cardboard"):
        raise AssertionError(f'Survival crafting left unused Cardboard for {item}')
    source = crafting.inventory_slot(actor, item)
    if source != 0:
        actor.call("click-slot", source)
        actor.call("click-slot", 0)
    actor.call("close")
    world.command(f"/tp {player} 12.5 170 26.5 0 0")
    actor.call("look-at", 12.5, 171.6, 29)
    actor.call("key", "1", "tap")
    mp.until("the crafter to hold the new armor", lambda: (actor.call("inventory")["held"] or {}).get("item") == item)
    actor.call("use-item")
    slot = SLOTS[item.split("_", 1)[1]]
    mp.until("the new armor to equip", lambda:
             f'id: "{item}"' in world.command(f"/data get entity {player} equipment.{slot}"))
    reply = world.command(f"/attribute {player} minecraft:armor get")
    defense = float(reply.split()[-1])
    if defense != int(reference["defense"]):
        raise AssertionError(f'{item} gives {defense} defense, expected {reference["defense"]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/cardboard-armor-java.csv").open(newline="") as source:
        references = list(csv.DictReader(source))
    with ExitStack() as stack:
        scenario = "CardboardArmorLAN" if args.lan else "CardboardArmor"
        world = stack.enter_context(fixture_world(args, scenario, render=True, pack=args.pack))
        world.commands((
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
        ))
        actor, player = world, "@s"
        if args.lan:
            world.command("/tp @s 9.5 170 25.5")
            player = "ArmorGuest"
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            directory = Path(stack.enter_context(TemporaryDirectory(prefix="hc-arm-")))
            actor = stack.enter_context(mp.joined_client(
                args, directory, f"127.0.0.1:{port}", player,
                render=True, scenario="cardboard-armor", pack=args.pack,
            ))
            mp.until("the crafter to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in world.call("lan", "status")["guests"]
            ))
            world.command(f"/tp {player} 12.5 170 26.5")
            mp.until("the crafter to reach the table", lambda:
                     tuple(actor.call("state")["player"]["position"]) == (12.5, 170, 26.5))
        world.command(f"/gamemode survival {player}")
        for reference in references:
            replay(world, actor, player, reference)
    print(f"All {len(references)} Java Cardboard armor recipes, equipment slots and defense values matched.")


if __name__ == "__main__":
    main()
