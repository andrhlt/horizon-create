#!/usr/bin/env python3
"""Check original Bound Block of Cardboard survival behavior and both fuels."""
import argparse
from contextlib import contextmanager
from importlib import import_module
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

crafting = import_module("test-survival-crafting")
placement = import_module("test-cardboard-placement")
recycle = import_module("test-window-recycling")
multiplayer = import_module("test-multiplayer")
fire = import_module("test-cardboard-fire")
PLAIN = "create:cardboard_block"
BOUND = "create:bound_cardboard_block"
CARDBOARD = "create:cardboard"
STRING = "minecraft:string"
ITEMS = (PLAIN, BOUND)
AT = "8 105 -12"
FURNACE = (8, 105, -14)
DROP_AREA = "@e[type=minecraft:item,x=6,y=103,z=-15,dx=4,dy=6,dz=6]"


def read_oracle():
    place = {item: [] for item in ITEMS}
    burn = {}
    drops = {}
    fires = []
    with (ROOT / "fixtures/bound-cardboard-java.txt").open() as stream:
        for line in stream:
            kind, row = line.strip().split(" ", 1)
            item, first, second, *rest = row.split(",")
            if kind == "PLACE":
                place[item].append({"yaw": first, "axis": second, "held": rest[0]})
            elif kind == "RULES":
                burn[item] = int(first)
            elif kind == "DROPS":
                items = [entry.split("*") for entry in second.split(";")]
                drops[item, first] = {name: int(count) for name, count in items}
            elif kind == "FIRE":
                fires.append({"support": item, "adjacent": first, "tool_damage": second})
    return place, burn, drops, fires


def craft(world, actor, name):
    set_up(world, (
        f"/item replace entity {name} hotbar.0 with {PLAIN}",
        f"/item replace entity {name} hotbar.1 with {STRING}",
    ))
    multiplayer.until("the Block of Cardboard and String to reach the player", lambda:
        multiplayer.count(actor, PLAIN) == 1 and multiplayer.count(actor, STRING) == 1)
    actor.call("open-inventory")
    actor.call("click-slot", crafting.inventory_slot(actor, PLAIN))
    actor.call("click-slot", 100)
    assert_result(actor, CARDBOARD, 4, "a Cardboard Block without String")
    crafting.craft(actor, CARDBOARD, 4)

    # Three sheets must not consume inputs or expose a block; the fourth
    # completes the original 2x2 construction recipe.
    source = crafting.inventory_slot(actor, CARDBOARD)
    crafting.distribute(actor, source, (100, 101, 102))
    assert_no_result(actor, "three-of-four Cardboard Block inputs")
    actor.call("click-slot", 103)
    crafting.craft(actor, PLAIN, 1)

    # With no String, the block conversion remains available, but binding
    # must wait until the String ingredient is added.
    actor.call("click-slot", crafting.inventory_slot(actor, PLAIN))
    actor.call("click-slot", 100)
    assert_result(actor, CARDBOARD, 4, "a Cardboard Block without String")
    actor.call("click-slot", 1)
    actor.call("click-slot", 101)
    crafting.craft(actor, BOUND, 1)
    counts = actor.call("inventory")["counts"]
    assert counts.get(BOUND) == 1 and counts.get(PLAIN, 0) == 0 and counts.get(STRING, 0) == 0, counts

    crafting.distribute(actor, crafting.inventory_slot(actor, BOUND), (100,))
    crafting.craft(actor, CARDBOARD, 4)
    counts = actor.call("inventory")["counts"]
    assert counts.get(CARDBOARD) == 4 and counts.get(BOUND, 0) == 0, counts
    actor.call("close")
    multiplayer.until("Cardboard recipes to conserve exact inputs and outputs", lambda:
        multiplayer.count(actor, CARDBOARD) == 4 and not any(
            multiplayer.count(actor, item) for item in (PLAIN, STRING, BOUND)))


def assert_no_result(actor, case):
    result = next((entry.get("stack") for entry in actor.call("menu")["slots"]
                   if entry["slot"] == 200), None)
    if result:
        raise AssertionError(f"{case} unexpectedly exposed a crafting result: {result}")


def assert_result(actor, item, count, case):
    result = next((entry.get("stack") for entry in actor.call("menu")["slots"]
                   if entry["slot"] == 200), None)
    actual = (result["item"], result["count"]) if result else None
    if actual != (item, count):
        raise AssertionError(f"{case} expected {(item, count)}, got {actual}")


def set_up(world, commands):
    world.call('script', script=''.join(f'command {json.dumps(cmd)}\n' for cmd in commands))


def break_block(world, actor, name, item, kind, expected):
    tool = {
        "hand": "minecraft:air",
        "axe": "minecraft:iron_axe",
        "silk": 'minecraft:diamond_axe[minecraft:enchantments={"minecraft:silk_touch":1}]',
    }[kind]
    set_up(world, (
        f"/kill {DROP_AREA}",
        f"/clear {name}",
        f"/setblock {AT} {item}[axis=x]",
        f"/item replace entity {name} hotbar.0 with {tool}",
        f"/tp {name} 8.5 105 -9.5",
    ))
    multiplayer.until("the original tool and placed block to reach the player", lambda:
        actor.call("block", 8, 105, -12)["block"] == item
        and ((actor.call("inventory")["held"] or {}).get("item") or "minecraft:air") == tool.split("[")[0])
    actor.call("look-at", 8.5, 105.5, -11.5)
    actor.call("mouse", "left", "down")
    try:
        for _ in range(30):
            world.step_to(world.clock() + 1)
            actor.call("wait", 1)
            if world.command(f"/execute if block {AT} minecraft:air") == "Test passed":
                break
        else:
            raise RuntimeError(f"Player could not harvest {item} with {kind}.")
    finally:
        actor.call("mouse", "left", "up")
    world.step_to(world.clock() + 1)
    def drops():
        result = {}
        for entry in actor.call("entities", 7, "minecraft:item")["entities"]:
            if item_stack := entry.get("item"):
                key = item_stack["item"]
                result[key] = result.get(key, 0) + item_stack["count"]
        for key in (PLAIN, BOUND, STRING):
            selector = DROP_AREA[:-1] + ',nbt={Item:{id:' + json.dumps(key) + ',count:1}}]'
            authoritative = world.command(f"/execute if entity {selector}")
            if authoritative.startswith("Test passed") != (result.get(key) == 1):
                return None
        return result

    try:
        multiplayer.until(f"physical loot for {item} with {kind}", lambda: drops() == expected)
    except RuntimeError:
        pass
    actual = drops()
    print(f"{item} with {kind}: Java {expected}, Horizon {actual}", flush=True)
    return actual == expected


def fuels(world, actor, name, expected):
    x, y, z = FURNACE
    at = f"{x} {y} {z}"
    world.command(f"/tp {name} {x+.5} {y} {z+2.5}")
    for item, duration in expected.items():
        set_up(world, (
            f"/clear {name}",
            f"/setblock {at} minecraft:air",
            f"/setblock {at} minecraft:furnace",
            f"/item replace block {at} container.0 with minecraft:raw_iron",
            f"/item replace entity {name} hotbar.0 with {item}",
        ))
        multiplayer.until("the Cardboard fuel reaches the player", lambda:
            (actor.call("inventory")["held"] or {}).get("item") == item)
        actor.call("interact", *FURNACE, "south")
        actor.call("click-slot", 0)
        actor.call("click-slot", 301)
        multiplayer.until("the original block enters the fuel slot", lambda:
            any(entry["slot"] == 301 and (entry["stack"] or {}).get("item") == item
                for entry in actor.call("menu")["slots"]))
        start = world.clock()
        for tick in range(1, 5):
            world.step_to(start + tick)
            tag = world.command(f"/data get block {at}")
            row = recycle.read_furnace(tick, item, tag, "")
            assert row[2:5] == (str(tick), "200", str(duration + 1 - tick)), (item, row)
        actor.call("close")
        print(f"{item} starts its original {duration}-tick fuel budget.", flush=True)


@contextmanager
def operator(world, args, scratch):
    if not args.lan:
        yield world, "@s"
        return
    name = "BoundGuest"
    world.command("/tp @s 12.5 105 -8.5")
    port = world.call("lan", "open", 0, "commands", "force")["port"]
    with multiplayer.joined_client(
        args, Path(scratch), f"127.0.0.1:{port}", name, render=args.menus,
        scenario="cardboard-bound", pack=args.pack,
    ) as actor:
        multiplayer.until("the Bound Cardboard guest joins", lambda: any(
            guest["name"] == name and guest["placed"] for guest in world.call("lan", "status")["guests"]
        ))
        yield actor, name


def main():
    os.environ.setdefault("HORIZON_NO_AUDIO", "1")
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--menus", action="store_true")
    args = parser.parse_args()
    placements, burn, drops, fires = read_oracle()
    with TemporaryDirectory(prefix="hc-bound-cardboard-") as scratch:
        scenario = "BoundCardboard" + ("Menus" if args.menus else "") + ("LAN" if args.lan else "")
        with fixture_world(args, scenario, render=args.menus and not args.lan, pack=args.pack) as world:
            if args.baseline:
                reply = world.command(f"/execute if block ~ ~ ~ {BOUND}")
                assert "<--[HERE]" in reply, reply
                print("The installed baseline lacks the original Bound Block of Cardboard ID.")
                return
            with operator(world, args, scratch) as (actor, name):
                if args.menus:
                    set_up(world, (
                        "/fill 4 104 -17 14 104 -7 minecraft:smooth_stone",
                        f"/gamemode survival {name}",
                        f"/tp {name} 8.5 105 -11.5",
                    ))
                    craft(world, actor, name)
                    fuels(world, actor, name, burn)
                    print("Matched the original binding recipe and both 4,000-tick fuel budgets.")
                    return
                for item, rows in placements.items():
                    placement.place(world, actor, name, rows, item=item, prepare=item == PLAIN)
                compared = []
                for (item, kind), expected in drops.items():
                    compared.append(break_block(world, actor, name, item, kind, expected))
                set_up(world, (
                    "/fill 4 107 -18 16 114 -4 minecraft:air",
                    "/fill 11 108 -16 14 108 -6 minecraft:stone",
                ))
                for row, z in zip(fires, (-12, -8), strict=True):
                    fire.ignite(world, actor, name, row, z)
                if not all(compared):
                    raise RuntimeError(f"{compared.count(False)} Java drop mismatch(es).")
    print("Matched four original placement results, six harvest results, and both ignition cases.")


if __name__ == "__main__":
    main()
