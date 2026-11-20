#!/usr/bin/env python3
"""Observe Create's inventory advancements on the original action ticks."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
GUEST = "AdvGuest"
LOG = (12, 171, 24)


def progress(world, target, advancements):
    selector, filters = ("@s", "") if target == "@s" else ("@a", f"name={target},")
    replies = world.commands(
        f"/execute if entity {selector}[{filters}advancements={{create:{name}=true}}]"
        for name in advancements
    )
    return tuple(str(reply.startswith("Test passed")).lower() for reply in replies)


def apply_casing(world, actor, tick, start, target, advancements):
    actor.call("select", "create:andesite_alloy")
    actor.call("look-at", "block", *LOG)
    actor.call("mouse", "right", "click")
    multiplayer.until("the stripped log to turn into andesite casing",
                      lambda: world.call("block", *LOG)["state"] == "create:andesite_casing")
    multiplayer.until("the alloy to be consumed",
                      lambda: not actor.call("inventory")["counts"].get("create:andesite_alloy", 0))
    if world.clock() != start + tick or progress(world, target, advancements)[-1] != "true":
        raise RuntimeError("The casing advancement did not award on the application tick.")


def replay(world, actor, target, rows, advancements, casing):
    world.command(f"/gamemode survival {target}")
    if casing:
        world.commands((
            "/fill 8 170 22 16 170 28 minecraft:stone",
            "/setblock 12 171 24 minecraft:stripped_oak_log",
            f"/tp {target} 12.5 171 26.5",
        ))
        actor.call("wait", 3)
    start = world.clock()
    differences = []
    for row in rows:
        tick = int(row["tick"])
        world.step_to(start + tick)
        actual = progress(world, target, advancements)
        expected = tuple(row[name] for name in advancements)
        if actual != expected:
            differences.append((tick, expected, actual))
        if tick == 4:
            world.command(f"/give {target} minecraft:stick")
        elif tick == 8:
            world.command(f"/give {target} create:andesite_alloy")
        elif tick == 11 and casing:
            apply_casing(world, actor, tick, start, target, advancements)
    if differences:
        raise RuntimeError(f"{len(differences)} advancement ticks differ. First: {differences[:5]}")
    print(f"Original advancement criteria matched all {len(rows)} Java ticks.")


def apply_material_casings(world, actor, target):
    materials = (
        ("andesite", "create:andesite_alloy"),
        ("brass", "create:brass_ingot"),
        ("copper", "minecraft:copper_ingot"),
    )
    cases = []
    commands = ["/fill 8 170 22 16 170 28 minecraft:stone"]
    for index, (material, ingredient) in enumerate(materials):
        # Each Java recipe accepts both a stripped log and stripped wood.
        for wood, block in (("log", "minecraft:stripped_oak_log"),
                            ("wood", "minecraft:stripped_oak_wood")):
            pos = (9 + index * 2 + (wood == "wood"), 171, 24)
            commands.append(f"/setblock {' '.join(map(str, pos))} {block}")
            cases.append((material, ingredient, pos, f"create:{material}_casing"))
        commands.append(f"/item replace entity {target} hotbar.{index} with {ingredient} 2")
    world.commands(commands)
    for index, (material, ingredient, pos, casing) in enumerate(cases):
        actor.call("select", ingredient)
        sneaking = index % 2 == 1
        if sneaking:
            actor.call("key", "shift", "down")
        try:
            actor.call("look-at", "block", *pos)
            actor.call("mouse", "right", "click")
        finally:
            if sneaking:
                actor.call("key", "shift", "up")
        multiplayer.until(f"the {material} casing application at {pos}",
                          lambda: world.call("block", *pos)["state"] == casing)
        remaining = actor.call("inventory")["counts"].get(ingredient, 0)
        expected = 1 if index % 2 == 0 else 0
        if remaining != expected:
            raise RuntimeError(f"{material} application left {remaining} {ingredient}, expected {expected}.")
    return tuple((pos, casing) for _, _, pos, casing in cases)


def check_casing_pickup(world, pos, casing, tool):
    x, y, z = pos
    before = world.call("inventory")["counts"].get(casing, 0)
    world.commands((f"/tp @s {x + 0.5} {y} {z + 2.5}",
                    f"/item replace entity @s hotbar.8 with {tool}"))
    world.call("wait", 3)
    world.call("select", tool)
    world.call("look-at", x + 0.5, y + 0.5, z + 0.5)
    world.call("mouse", "left", "down")
    try:
        for _ in range(120):
            world.step_to(world.clock() + 1)
            if world.command(f"/execute if block {x} {y} {z} minecraft:air").startswith("Test passed"):
                break
        else:
            raise RuntimeError(f"Survival mining did not remove {casing}.")
    finally:
        world.call("mouse", "left", "up")
    world.step_to(world.clock() + 1)
    world.call("wait", 3)
    drops = world.call("entities", 8, "minecraft:item")["entities"]
    if [drop["item"]["count"] for drop in drops if drop["item"]["item"] == casing] != [1]:
        raise RuntimeError(f"Mining {casing} with {tool} produced unexpected drops: {drops}")
    world.command(f"/tp @s {x + 0.5} {y} {z + 0.5}")
    for _ in range(20):
        world.step_to(world.clock() + 1)
    multiplayer.until(f"one mined {casing} in inventory",
                      lambda: world.call("inventory")["counts"].get(casing, 0) == before + 1)
    print(f"Survival mining and pickup returned one {casing}.")


def run(args):
    fixture = "casing-advancement" if args.casing else "first-advancements"
    with (ROOT / f"fixtures/{fixture}-java.csv").open() as source:
        reader = csv.DictReader(source)
        advancements = reader.fieldnames[1:]
        rows = list(reader)
    scenario = f"{fixture}-lan" if args.multiplayer else fixture
    with fixture_world(args, scenario, render=True, pack=args.pack) as world:
        if not args.multiplayer:
            replay(world, world, "@s", rows, advancements, args.casing)
            applied = apply_material_casings(world, world, "@s") if args.casing else ()
            world.restart()
            if progress(world, "@s", advancements) != ("true",) * len(advancements):
                raise RuntimeError("The earned advancements were lost on reopen.")
            for pos, casing in applied:
                if world.call("block", *pos)["state"] != casing:
                    raise RuntimeError(f"Applied {casing} did not persist after reopening at {pos}.")
            print("Earned advancements persisted after reopening the world.")
            if applied:
                print(f"All {len(applied)} casing states persisted after reopening.")
                world.call("command", "/gamemode survival @s")
                for index, (pos, casing) in enumerate(applied):
                    tool = "minecraft:diamond_axe" if index % 2 == 0 else "minecraft:diamond_pickaxe"
                    check_casing_pickup(world, pos, casing, tool)
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-adv-") as folder, multiplayer.joined_client(
            args, Path(folder), f"127.0.0.1:{port}", GUEST,
            render=True, scenario="adv", pack=args.pack,
        ) as guest:
            multiplayer.until("the advancement guest to join", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in world.call("lan", "status")["guests"]
            ))
            replay(world, guest, GUEST, rows, advancements, args.casing)
            if progress(world, "@s", advancements) != ("false",) * len(advancements):
                raise RuntimeError("The guest's awards also advanced the host.")
            if args.casing:
                for pos, casing in apply_material_casings(world, guest, GUEST):
                    multiplayer.until(f"the guest to see {casing} at {pos}",
                                      lambda: guest.call("block", *pos)["state"] == casing)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    parser.add_argument("--casing", action="store_true")
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
