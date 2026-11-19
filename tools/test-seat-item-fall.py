#!/usr/bin/env python3
"""Compare the original Create seat bounce for a dropped ingot."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

ejector = import_module("test-depot-ejector-obstacle")
multiplayer = import_module("test-multiplayer")
ORIGIN_Y = 171
GUEST = "DropGuest"
INGOT = "minecraft:iron_ingot"
DUMMY = "minecraft:gold_ingot"


def align_entity_phase(host, phase):
    for count in range(1, 5):
        host.command(f'/summon minecraft:item 12.5 174 23.5 {{Item:{{id:"{DUMMY}",count:1}},PickupDelay:32767s}}')
        ids = multiplayer.until("the alignment items to appear", lambda:
                                ids if len(ids := ejector.item_ids(host, DUMMY)) == count else None)
        if (max(ids) + 1) % 4 == phase:
            break
    else:
        raise RuntimeError(f"Could not allocate a dropped item with Java phase {phase}.")
    host.command(f'/kill @e[type=minecraft:item,nbt={{Item:{{id:"{DUMMY}"}}}}]')


def exercise(host, expected, guest=None):
    phase = int(expected[0]["phase"])
    align_entity_phase(host, phase)
    host.command(f'/summon minecraft:item 9.5 174.25 21.5 '
                 f'{{Item:{{id:"{INGOT}",count:1}},Motion:[0.0d,0.0d,0.0d],Tags:["SeatIngot"],PickupDelay:32767s}}')
    ids = multiplayer.until("the test ingot to appear", lambda: ejector.item_ids(host, INGOT))
    if len(ids) != 1 or ids[0] % 4 != phase:
        raise RuntimeError(f"Java item phase {phase}, Horizon entity IDs {ids}.")
    start = host.clock()
    errors = []
    for row in expected:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        nbt = host.command("/data get entity @e[tag=SeatIngot,limit=1]")
        position, motion = (ejector.vector(nbt, key) for key in ("Pos", "Motion"))
        ground = re.search(r"\bOnGround: (true|false|[01]b)", nbt)
        if not position or not motion or not ground:
            raise RuntimeError(f"Could not read ingot state at tick {tick}: {nbt}")
        y = position[1] - ORIGIN_Y
        grounded = ground[1] in ("true", "1b")
        if (abs(y - float(row["y"])) > 2e-7 or abs(motion[1] - float(row["vy"])) > 2e-7
                or grounded != (row["grounded"] == "true")):
            errors.append((row, y, motion[1], grounded))
    if guest:
        multiplayer.until("the guest to see the same resting ingot", lambda: any(
            item["id"] == ids[0] and abs(item["pos"][1] - float(expected[-1]["y"]) - ORIGIN_Y) < .002
            for item in ejector.items_near(guest, INGOT)
        ))
    if errors:
        raise RuntimeError(f"Seat item differed at {len(errors)} ticks. First {errors[:3]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/seat-item-fall-java.csv").open() as source:
        expected = list(csv.DictReader(source))
    with fixture_world(args, "Seat item physics", render=args.lan, pack=args.pack) as host:
        host.commands((
            "/fill 6 170 18 13 170 25 minecraft:stone",
            "/setblock 9 171 21 create:red_seat",
            "/tp @s 9.5 171 24.5",
        ))
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-drop-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="seat-item-drop", pack=args.pack,
            ) as actor:
                multiplayer.until("the item guest to join", lambda: any(
                    p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]
                ))
                host.command(f"/tp {GUEST} 10.5 171 23.5")
                exercise(host, expected, actor)
        else:
            exercise(host, expected)
    print(f"Seat item position, velocity and ground state matched all {len(expected)} Java ticks.")


if __name__ == "__main__":
    main()
