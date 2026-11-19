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
            world.restart()
            if progress(world, "@s", advancements) != ("true",) * len(advancements):
                raise RuntimeError("The earned advancements were lost on reopen.")
            print("Earned advancements persisted after reopening the world.")
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    parser.add_argument("--casing", action="store_true")
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
