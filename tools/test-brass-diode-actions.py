#!/usr/bin/env python3
"""Replay Java Create Brass Diode recipes and physical actions in Horizon survival."""
import argparse
from collections import defaultdict
from contextlib import ExitStack
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
crafting = import_module("test-survival-crafting")
state_properties = import_module("test-stone-palettes").state_properties
REFERENCE = ROOT / "fixtures/brass-diode-actions-java.json"
TAG_EXAMPLES = {
    "c:plates/brass": "create:brass_sheet",
    "c:dusts/redstone": "minecraft:redstone",
    "c:stones": "minecraft:stone",
}
TABLE = (10, 170, 24)
BLOCK = (12, 170, 24)
OUT = (12, 170, 23)
SIDE = (13, 170, 24)
POSITION = (12.5, 170, 26.5)


def coords(pos):
    return " ".join(map(str, pos))


def craft(world, actor, player, recipe):
    cells = defaultdict(list)
    for row, line in enumerate(recipe["pattern"]):
        for col, letter in enumerate(line):
            if letter == " ":
                continue
            key = recipe["key"][letter]
            ingredient = key["item"] if "item" in key else TAG_EXAMPLES[key["tag"]]
            cells[ingredient].append(100 + row * 3 + col)
    world.commands((
        f"/clear {player}",
        *(f"/item replace entity {player} hotbar.{slot} with {ingredient} {len(slots)}"
          for slot, (ingredient, slots) in enumerate(cells.items())),
    ))
    for ingredient, slots in cells.items():
        mp.until(f"{player} to receive {ingredient}", lambda: mp.count(actor, ingredient) == len(slots))
    actor.call("interact", *TABLE, "up")
    for source, slots in enumerate(cells.values()):
        crafting.distribute(actor, source, slots)
    item, count = recipe["result"]["id"], recipe["result"]["count"]
    crafting.output(actor, item, count)
    actor.call("click-slot", 200, "shift")
    mp.until(f"{player} to craft {item}", lambda: mp.count(actor, item) == count)
    if any(mp.count(actor, item) for item in cells):
        raise AssertionError("Recipe left an unspent ingredient")
    source = crafting.inventory_slot(actor, item)
    if source != 0:
        actor.call("click-slot", source)
        actor.call("click-slot", 0)
    actor.call("close")
    print("craft", "/".join(recipe["pattern"]), item, count, flush=True)


def click(actor, aim, target):
    actor.call("look-at", *aim)
    mp.until(f"{target} to be targeted", lambda: (actor.call("looking-at").get("block") or {}).get("pos") == list(target))
    actor.call("mouse", "right", "click")


def read(peer):
    flags = state_properties(peer.call("block", *BLOCK)["state"])
    out, side = (state_properties(peer.call("block", *pos)["state"]) for pos in (OUT, SIDE))
    return (
        flags["facing"], flags["powering"] == "true", flags["inverted"] == "true",
        int(out["power"]), int(side["power"]),
    )


def observe(world, actor, item, action, expected):
    want = expected[item, action]
    facing, powering, inverted, front, side = want
    flags = f"facing={facing},powering={str(powering).lower()},inverted={str(inverted).lower()}"
    states = (
        (BLOCK, f"{item}[{flags}]"),
        (OUT, f"minecraft:redstone_wire[power={front}]"),
        (SIDE, f"minecraft:redstone_wire[power={side}]"),
    )
    authority = world.commands(f"/execute if block {coords(pos)} {state}" for pos, state in states)
    host_view = read(world)
    player_view = host_view
    if actor is not world:
        mp.until("guest to receive the host's diode and wire states", lambda: read(actor) == host_view)
        player_view = read(actor)
    print(
        f"{item} {action}: Java {want}, authority {authority}, "
        f"host view {host_view}, actor view {player_view}",
        flush=True,
    )
    return authority == ["Test passed"] * len(states) and host_view == player_view == want


def replay(world, actor, player, recipe, expected):
    item = recipe["result"]["id"]
    world.commands((
        f"/setblock {coords(BLOCK)} minecraft:air",
        f"/setblock {coords(OUT)} minecraft:redstone_wire",
        f"/setblock {coords(SIDE)} minecraft:redstone_wire",
    ))
    craft(world, actor, player, recipe)
    actor.call("select", item)
    click(actor, (12.5, 170, 24.5), (12, 169, 24))
    mp.until(f"{item} to be placed by {player}", lambda: world.call("block", *BLOCK)["block"] == item)
    mp.until(f"{player} to spend the crafted diode", lambda: mp.count(actor, item) == 0)
    actor.call("wait", 2)
    passed = [observe(world, actor, item, "place", expected)]
    aim = (12.5, 170.1, 24.5)
    actor.call("key", "shift", "down")
    try:
        actor.call("wait", 4)
        click(actor, aim, BLOCK)
        actor.call("wait", 4)
        passed.append(observe(world, actor, item, "sneak-empty", expected))
    finally:
        actor.call("key", "shift", "up")
    actor.call("wait", 4)
    click(actor, aim, BLOCK)
    actor.call("wait", 4)
    passed.append(observe(world, actor, item, "empty-hand", expected))
    world.command(f"/item replace entity {player} hotbar.0 with minecraft:stick")
    mp.until("the survival player to hold a stick", lambda: (actor.call("inventory")["held"] or {}).get("item") == "minecraft:stick")
    click(actor, aim, BLOCK)
    actor.call("wait", 4)
    passed.append(observe(world, actor, item, "stick", expected))
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    reference = json.loads(REFERENCE.read_text())
    expected = {
        (row["item"], row["action"]): (
            row["facing"], row["powering"], row["inverted"], row["front_power"], row["side_power"],
        )
        for row in reference["actions"]
    }
    results = []
    with ExitStack() as stack:
        scenario = "BrassDiodeActionsLAN" if args.lan else "BrassDiodeActions"
        world = stack.enter_context(fixture_world(args, scenario, render=True, pack=args.pack))
        world.commands((
            "/fill 8 169 20 16 169 29 minecraft:smooth_stone",
            f"/setblock {coords(TABLE)} minecraft:crafting_table",
            f"/tp @s {coords(POSITION)} 180 25",
        ))
        actor, player = world, "@s"
        if args.lan:
            player = "DiodeBuilder"
            world.command("/tp @s 14.5 170 26.5")
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            directory = Path(stack.enter_context(TemporaryDirectory(prefix="hc-diode-actions-")))
            actor = stack.enter_context(mp.joined_client(
                args, directory, f"127.0.0.1:{port}", player,
                render=True, scenario="brass-diode-actions", pack=args.pack,
            ))
            mp.until("the crafter to join", lambda: any(
                guest["name"] == player and guest["placed"] for guest in world.call("lan", "status")["guests"]
            ))
            world.command(f"/tp {player} {coords(POSITION)} 180 25")
            mp.until("the crafter to reach the table", lambda:
                     tuple(actor.call("state")["player"]["position"]) == POSITION)
        world.command(f"/gamemode survival {player}")
        for recipe in reference["recipes"]:
            results.extend(replay(world, actor, player, recipe, expected))
    print(f"{len(reference['recipes'])} original recipes crafted. "
          f"{sum(results)}/{len(results)} physical action states matched.", flush=True)
    raise SystemExit(not all(results))


if __name__ == "__main__":
    main()
