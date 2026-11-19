#!/usr/bin/env python3
"""Compare a falling pig's original Create Seat ride and dismount."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

ejector = import_module("test-depot-ejector-obstacle")
multiplayer = import_module("test-multiplayer")
ORIGIN = (9, 171, 21)
GUEST = "SeatWatcher"


def pigs(actor):
    return [mob for mob in actor.call("mobs", 12)["near"] if mob["kind"] == "minecraft:pig"]


def passenger(mob):
    return mob["mount"] is not None and mob["passenger"]


def motion_y(host, selector):
    nbt = host.command(f"/data get entity {selector}")
    velocity = ejector.vector(nbt, "Motion")
    if velocity is None:
        raise RuntimeError(f"Pig velocity missing: {nbt}")
    return velocity[1]


def exercise(host, expected, guest=None):
    host.command('/summon minecraft:pig 9.5 174.25 21.5')
    host.command("/attribute @e[type=minecraft:pig,limit=1] minecraft:movement_speed base set 0")
    start = host.clock()
    mismatches = []
    for row in expected:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        mob = next(iter(pigs(host)), None)
        if mob is None:
            raise RuntimeError(f"Pig missing at tick {tick}.")
        position = [pos - origin for pos, origin in zip(mob["pos"], ORIGIN, strict=True)]
        numbers = (*position, motion_y(host, "@e[type=minecraft:pig,limit=1]"), mob["health"])
        same = all(abs(value - float(row[key])) < 2e-7 for value, key in zip(
            numbers, ("x", "y", "z", "vy", "health"), strict=True
        ))
        if not same or mob["on_ground"] != (row["grounded"] == "true") or passenger(mob) != (row["passenger"] == "true"):
            mismatches.append((tick, numbers, mob["on_ground"], passenger(mob)))
        if tick == 16 and guest and passenger(mob):
            multiplayer.until("the guest to see the pig riding", lambda: any(passenger(mob) for mob in pigs(guest)))
        if tick == 24:
            host.command("/setblock 9 171 21 minecraft:air")
    if mismatches:
        raise RuntimeError(f"Pig differed at {len(mismatches)} ticks. First {mismatches[:3]}.")
    if guest:
        multiplayer.until("the guest to see the pig dismount", lambda: bool(pigs(guest)) and not any(passenger(mob) for mob in pigs(guest)))


def occupied_seat(host, expected):
    ids = {}
    cases = {0: ("occupant", 180.25), 22: ("newcomer", 174.25)}
    mismatches = []
    start = host.clock()
    for row in expected:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        if tick in cases:
            role, y = cases[tick]
            host.command(f'/summon minecraft:pig 9.5 {y} 21.5 {{Tags:["{role}"]}}')
            fresh, = [mob for mob in pigs(host) if mob["id"] not in ids.values()]
            ids[role] = fresh["id"]
        mobs = {mob["id"]: mob for mob in pigs(host)}
        for role, mob_id in ids.items():
            mob = mobs[mob_id]
            selector = f"@e[tag={role},limit=1]"
            state = mob["pos"][1] - ORIGIN[1], motion_y(host, selector), mob["health"]
            numbers = tuple(float(row[f"{role}_{field}"]) for field in ("y", "vy", "health"))
            flags = mob["on_ground"], passenger(mob)
            expected_flags = tuple(row[f"{role}_{field}"] == "true" for field in ("grounded", "passenger"))
            if flags != expected_flags or any(abs(a - b) > 2e-7 for a, b in zip(state, numbers, strict=True)):
                mismatches.append((tick, role, state, flags, numbers, expected_flags))
    if mismatches:
        raise RuntimeError(f"Occupied Seat differs at {len(mismatches)} samples. First {mismatches[:3]}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    roles = parser.add_mutually_exclusive_group()
    roles.add_argument("--lan", action="store_true")
    roles.add_argument("--occupied", action="store_true")
    args = parser.parse_args()
    filename = "seat-mob-rival-java.csv" if args.occupied else "seat-mob-landing-java.csv"
    with (ROOT / "fixtures" / filename).open() as source:
        expected = list(csv.DictReader(source))
    with fixture_world(args, "Seat pig landing", render=args.lan, pack=args.pack) as host:
        host.commands((
            "/fill 6 170 18 13 170 25 minecraft:stone",
            "/setblock 9 171 21 create:red_seat",
            "/tp @s 9.5 171 24.5",
            "/gamerule spawn_mobs false",
        ))
        if args.occupied:
            occupied_seat(host, expected)
        elif args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-seat-pig-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="seat-pig-landing", pack=args.pack,
            ) as guest:
                multiplayer.until("the guest to join", lambda: any(
                    player["name"] == GUEST and player["placed"]
                    for player in host.call("lan", "status")["guests"]
                ))
                host.command(f"/tp {GUEST} 10.5 171 23.5")
                exercise(host, expected, guest)
        else:
            exercise(host, expected)
    print(f"Pig movement, health, floor contact and Seat passenger state matched {len(expected)} Java ticks.")


if __name__ == "__main__":
    main()
