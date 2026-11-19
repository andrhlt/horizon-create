#!/usr/bin/env python3
"""Compare Horizon Item Hatch placement, inventory transfers and close timing to Java Create."""

import argparse
from collections import Counter
from contextlib import ExitStack
import csv
from importlib import import_module
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

craft = import_module("test-machine-crafting")
mp = import_module("test-multiplayer")
nozzle = import_module("test-nozzle")
trapdoors = import_module("test-train-trapdoors")
HATCH = "create:item_hatch"


def reference(name):
    with (ROOT / "fixtures" / f"item-hatch-{name}-java.csv").open(newline="") as file:
        return list(csv.DictReader(file))


def xyz(at):
    return nozzle.xyz(at)


def block(host, at, facing, opened, wet="false"):
    return nozzle.state(host, at) == f"{HATCH}[facing={facing},open={opened},waterlogged={wet}]"


def placement(host, actor, player, pack):
    with ZipFile(pack) as archive:
        shapes = json.loads(archive.read("data/create/horizon/block/item_hatch.json"))
    start = host.clock()
    for index, row in enumerate(reference("placement")):
        face = row["face"]
        offset = nozzle.OFFSETS[face]
        support = (5 + index * 5, 172, 23)
        destination = nozzle.add(support, offset)
        feet = (nozzle.add(support, (2.5, 2 if face == "up" else -4, .5)) if offset[1] else
                nozzle.add(support, (.5 + 3 * offset[0], -1, .5 + 3 * offset[2])))
        host.commands((
            f"/setblock {xyz(support)} minecraft:stone",
            f"/setblock {xyz(destination)} {'minecraft:water' if row['destination_water'] == 'true' else 'minecraft:air'}",
            f"/clear {player}",
            f"/item replace entity {player} hotbar.0 with {HATCH}",
        ))
        trapdoors.prepare_actor(host, actor, player, feet)
        mp.until("the Item Hatch to enter the hotbar", lambda: mp.count(actor, HATCH) == 1)
        actor.call("select", HATCH)
        nozzle.aim(actor, nozzle.add(support, (.5, .5, .5)), support, face)
        actor.call("wait", 2)
        actor.call("mouse", "right", "click")
        if row["result"] == "CONSUME":
            facing, wet = row["facing_and_waterlogged"].split(":")
            mp.until(f"the {face} Hatch state to match Java", lambda:
                     block(host, destination, facing, "false", wet) and block(actor, destination, facing, "false", wet))
            boxes = [[float(value) for value in box.split(":")] for box in row["outline"].split("+")]
            for key in ("shapes", "collision_shapes"):
                assert shapes[key]["values"][facing] == boxes, (row, key)
        else:
            actor.call("wait", 6)
            assert nozzle.state(host, destination) == "minecraft:air", row
        mp.until("the surviving Hatch stack count to match Java", lambda:
                 mp.count(actor, HATCH) == int(row["remaining"]))
        assert host.clock() == start, row
    print("All seven Java placement outcomes and four directional shapes matched.", flush=True)


def item_counts(host, at):
    if nozzle.state(host, at) == "minecraft:stone":
        return Counter()
    reply = host.command(f"/data get block {xyz(at)} Items")
    counts = Counter()
    for node in re.findall(r"\{[^{}]*\}", reply):
        item = re.search(r'\bid: "([^"]+)"', node)
        count = re.search(r"\bcount: (\d+)", node)
        if item and count:
            counts[item[1]] += int(count[1])
    return counts


def inventory_counts(actor):
    inventory = actor.call("inventory")
    slots = {stack["slot"]: stack.get("count", 0) for stack in inventory["hotbar"] + inventory["main"]}
    return tuple(slots[slot] for slot in (0, 1, 9, 10))


def deposit(host, actor, player):
    start = host.clock()
    for index, row in enumerate(reference("deposit")):
        name = row["scenario"]
        at = (7 + index * 5, 172, 33)
        x, y, z = at
        storage = (x, y, z - 1)
        host.commands((
            f"/setblock {xyz(storage)} minecraft:{'stone' if name == 'missing' else 'barrel'}",
            f"/setblock {xyz(at)} {HATCH}",
            f"/clear {player}",
            f"/item replace entity {player} hotbar.1 with minecraft:stick 7",
            f"/item replace entity {player} inventory.0 with minecraft:paper 3",
            f"/item replace entity {player} inventory.1 with minecraft:stick 4",
        ))
        if name != "empty_hand":
            host.command(f"/item replace entity {player} hotbar.0 with minecraft:paper 9")
        trapdoors.prepare_actor(host, actor, player, (x + .5, y - 1, z + 3.5))
        mp.until("the Item Hatch deposit inventory to be ready", lambda:
                 inventory_counts(actor) == (0 if name == "empty_hand" else 9, 7, 3, 4))
        actor.call("key", "1", "tap")
        if name in ("full", "partial"):
            fill = [f'{{Slot:{slot}b,id:"minecraft:stick",count:64}}' for slot in range(27)]
            if name == "partial":
                fill[5] = '{Slot:5b,id:"minecraft:paper",count:60}'
            host.command(f"/data merge block {xyz(storage)} {{Items:[{','.join(fill)}]}}")
        if name.startswith("filter_"):
            filtered = "stick" if name == "filter_reject" else "paper"
            host.command(f'/data merge block {xyz(at)} {{Filter:{{id:"minecraft:{filtered}",count:1}}}}')
        nozzle.aim(actor, (x + .5, y + .7, z + .2), at)
        sneaking = name == "sneak"
        if sneaking:
            actor.call("key", "shift", "down")
        try:
            nozzle.aim(actor, (x + .5, y + .7, z + .2), at)
            actor.call("wait", 2)
            actor.call("mouse", "right", "click")
            expected_slots = tuple(int(row[key]) for key in ("hotbar_0", "hotbar_1", "main_0", "main_1"))
            expected_counts = (int(row["paper_in_container"]), int(row["stick_in_container"]))
            if row["open"] == "false":
                actor.call("wait", 6)
            mp.until(f"{name} Hatch to match the original inventory transfer", lambda:
                     inventory_counts(actor) == expected_slots and block(host, at, "north", row["open"]))
            actual = item_counts(host, storage)
            assert (actual["minecraft:paper"], actual["minecraft:stick"]) == expected_counts, (name, actual, row)
            mp.until(f"{name} Hatch animation state to reach the client", lambda:
                     block(actor, at, "north", row["open"]))
        finally:
            if sneaking:
                actor.call("key", "shift", "up")
        assert host.clock() == start, (name, start, host.clock())
        print(f"{name}: inventory and open state matched Java.", flush=True)
    trapdoors.prepare_actor(host, actor, player, (7.5, 171, 36.5))
    for row in reference("timing"):
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        assert block(host, (7, 172, 33), "north", row["open"]), (tick, row)
        if actor is not host:
            mp.until(f"the guest to see the first Hatch at tick {tick}", lambda:
                     block(actor, (7, 172, 33), "north", row["open"]))
            assert host.clock() == start + tick, tick
    print("The Hatch stayed open for Java's ten-tick window.", flush=True)


def filter_input(host, actor, player):
    at = (7, 172, 33)
    host.commands(("/setblock 7 172 32 minecraft:barrel", f"/setblock {xyz(at)} {HATCH}"))
    trapdoors.prepare_actor(host, actor, player, (7.5, 171, 36.5))
    start = host.clock()
    for row in reference("filter"):
        name = row["action"]
        host.command(f"/clear {player}")
        stack = {"set": "minecraft:paper 3", "wrench": "create:wrench"}.get(name)
        if stack:
            host.command(f"/item replace entity {player} hotbar.0 with {stack}")
        actor.call("key", "1", "tap")
        count = int(row["held_count"])
        mp.until(f"the Hatch filter's {name} item to reach the player", lambda:
                 (actor.call("inventory")["held"] or {}).get("count", 0) == count)
        hit = nozzle.aim(actor, (7.5, 172.2, 33.2), at, "south")
        x, y, z = (a - b for a, b in zip(hit["point"], at, strict=True))
        assert abs(x - .5) < 1e-6 and abs(y - .204901) < .002 and abs(z - .2375) < 1e-7, hit
        actor.call("wait", 2)
        actor.call("mouse", "right", "click")
        actor.call("wait", 5)
        expected = int(row["filter_count"])

        def matches_filter():
            reply = host.command(f"/data get block {xyz(at)} Filter")
            if expected:
                return row["filter_item"] in reply and re.search(rf"\bcount: {expected}\b", reply)
            return reply.endswith("{}")

        try:
            mp.until(f"the Item Hatch filter to match Java after {name}", matches_filter, seconds=4)
        except RuntimeError as error:
            raise AssertionError((row, hit, host.command(f"/data get block {xyz(at)}"),
                                  actor.call("inventory")["held"])) from error
        assert (actor.call("inventory")["held"] or {}).get("count", 0) == count, row
        if row["claimed"] == "true":
            assert block(host, at, "north", "false") and not item_counts(host, (7, 172, 32)), row
        assert host.clock() == start, row
        print(f"{name}: Java filter and held stack matched via an actual value-box click.", flush=True)


def crafting(args, env):
    with fixture_world(args, "ItemHatchCraft", render=True, pack=args.pack, env=env) as host:
        host.commands(("/fill 8 169 22 16 169 28 minecraft:stone", "/setblock 12 170 24 minecraft:crafting_table",
                       "/tp @s 12.5 170 26.5", "/gamemode survival"))
        for row in reference("crafting"):
            craft.replay(host, {**row, "slots": row["inputs"].replace("|", ","), "remainder": ""})
    print("Original Item Hatch recipe matched in survival.")


def run(args):
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as stack:
        mode = "LAN" if args.lan else "Solo"
        host = stack.enter_context(fixture_world(args, f"ItemHatch{mode}", render=not args.lan,
                                                 pack=args.pack, env=env))
        actor, player = host, "@s"
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            player = "HatchGuest"
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-item-hatch-guest-")))
            actor = stack.enter_context(mp.joined_client(args, scratch, f"127.0.0.1:{port}", player,
                                                         scenario="item-hatch", pack=args.pack,
                                                         render=True, env=env))
            mp.until("the Hatch guest to join", lambda: any(guest["name"] == player and guest["placed"]
                     for guest in host.call("lan", "status")["guests"]))
        host.command(f"/gamemode survival {player}")
        if args.filter_only:
            filter_input(host, actor, player)
        else:
            placement(host, actor, player, args.pack)
            deposit(host, actor, player)
    if not args.lan and not args.filter_only:
        crafting(args, env)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--filter-only", action="store_true")
    run(parser.parse_args())
