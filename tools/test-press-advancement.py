#!/usr/bin/env python3
"""Verify the Mechanical Press awards its placer when another player operates it."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

advancement = import_module("test-first-advancements")
depot = import_module("test-depot-pressing")
multiplayer = advancement.multiplayer
GUEST = "PressGuest"
PRESS = "create:mechanical_press"
INGOT = "minecraft:iron_ingot"
SHEET = "create:iron_sheet"


def data_array(reply):
    return re.search(r"\[I; ([^\]]+)\]", reply)


def setup(host, owner, operator, placer, user):
    host.commands((
        "/fill 2 103 -14 11 103 -8 minecraft:smooth_stone",
        "/fill 67 103 -14 70 103 -8 minecraft:smooth_stone",
        f"/gamemode survival {placer}",
        f"/gamemode survival {user}",
        f"/tp {placer} 6.5 105 -10.5 90 0",
        f"/give {placer} {PRESS}",
        f"/setblock {depot.MOTOR} create:creative_motor[facing=east]{{ScrollValue:128}}",
        f"/setblock {depot.DEPOT} create:depot",
    ))
    multiplayer.until("the assigned player is holding a Press",
                      lambda: multiplayer.count(owner, PRESS) == 1)
    owner.call("select", PRESS)
    owner.call("interact", *map(int, depot.MOTOR.split()), "east")
    multiplayer.until("the owner placed a press on the motor",
                      lambda: host.call("block", *map(int, depot.PRESS.split()))["state"].startswith(PRESS))
    multiplayer.until("the owner consumed the block",
                      lambda: multiplayer.count(owner, PRESS) == 0)
    host.commands((f"/tp {placer} 69.5 104 -10.5",
                   f"/tp {user} 5.5 104 -8.5",
                   f"/give {user} {INGOT}"))
    for _ in range(5):
        host.step_to(host.clock() + 1)
    multiplayer.until("the operator received the iron ingot",
                      lambda: multiplayer.count(operator, INGOT) == 1)
    operator.call("select", INGOT)
    operator.call("interact", *map(int, depot.DEPOT.split()), "up")
    multiplayer.until("the operator loaded the Depot", lambda: INGOT in
                      host.command(f"/data get block {depot.DEPOT} Items"))
    selected = "@s" if placer == "@s" else f"@a[name={placer},limit=1]"
    owner_uuid = data_array(host.command(f"/data get entity {selected} UUID"))
    if owner_uuid is None:
        raise RuntimeError("Could not read the placer UUID")
    return owner_uuid[1]


def trace(host, owner_uuid, placer, user, expected):
    start = host.clock()
    failures = []
    for row in expected:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        press, item = host.commands((f"/data get block {depot.PRESS}", f"/data get block {depot.DEPOT} Items"))
        owner = re.search(r"\bOwner: \[I; ([^\]]+)\]", press)
        ownership = owner is not None and owner[1] == owner_uuid
        awards = tuple(advancement.progress(host, name, ("mechanical_press",))[0] for name in (placer, user))
        state = host.call("block", *map(int, depot.PRESS.split()))["state"]
        facing = re.search(r"facing=([a-z]+)", state)
        observed = (
            facing[1] if facing else "-",
            str(depot.scalar(press, "Speed")), str(depot.scalar(press, "Ticks")),
            str(ownership).lower(), str(SHEET in item).lower(), *awards,
        )
        want = tuple(row[field] for field in ("facing", "rpm", "cycle", "owns", "sheet", "placer", "operator"))
        if observed != want:
            failures.append((tick, want, observed))
        if host.clock() != start + tick:
            raise RuntimeError(f"Observing the award advanced the host tick at {tick}.")
    if failures:
        raise RuntimeError(f"{len(failures)} Press ownership ticks differ. First: {failures[:7]}")
    role = "host" if placer == "@s" else "guest"
    print(f"Only the {role} placer earned Bonk! across all {len(expected)} Java ticks.")


def run(args, scratch):
    with args.reference.open() as file:
        expected = list(csv.DictReader(file))
    with fixture_world(args, "PressAdvancement", depot.STRUCTURE, render=True, pack=args.pack) as host:
        network = host.call("lan", "open", "0", "commands", "force")
        with multiplayer.joined_client(
            args, scratch, f"127.0.0.1:{network['port']}", GUEST, render=True,
            scenario="press-advancement", pack=args.pack,
        ) as guest:
            multiplayer.until("guest entered", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            actors = [(host, "@s"), (guest, GUEST)]
            if args.guest_owner:
                actors.reverse()
            (owner, placer), (operator, user) = actors
            owner_uuid = setup(host, owner, operator, placer, user)
            trace(host, owner_uuid, placer, user, expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/press-advancement-java.csv")
    parser.add_argument("--guest-owner", action="store_true")
    with TemporaryDirectory(prefix="hc-press-award-") as directory:
        run(parser.parse_args(), Path(directory))
