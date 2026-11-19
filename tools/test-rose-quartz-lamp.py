#!/usr/bin/env python3
"""Replay Create's three-lamp cluster, redstone pulses and survival Wrench use."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

crafting = import_module("test-machine-crafting")
multiplayer = import_module("test-multiplayer")
LAMP = "create:rose_quartz_lamp"
GUEST = "LampGuest"
START = (9, 171, 20)
PULSES = {3: (2, True), 8: (2, False), 10: (0, True), 16: (0, False), 19: (1, True), 24: (1, False)}


def properties(actor, at):
    state = actor.call("block", *at)["state"]
    return dict(re.findall(r"(\w+)=(\w+)", state))


def sample(actor):
    x, y, z = START
    lamps = []
    for i in range(3):
        info = properties(actor, (x + i, y, z))
        flags = "".join("1" if info.get(key) == "true" else "0" if info.get(key) == "false" else "?"
                        for key in ("powered", "powering", "activate"))
        lamps.append(flags)
    powers = [properties(actor, (x + i, y, z)).get("power") for i in (-2, 4)]
    return [*lamps, *powers]


def lighting(actor, expected):
    x, y, z = START
    at = (x, y, z)
    return actor.call("light", *at, *at)["block"] == format(expected, "x")


def place_next_to_source(host, actor, player):
    at = (20, 171, 26)
    host.commands((
        "/setblock 20 170 26 minecraft:stone",
        "/setblock 20 170 28 minecraft:stone",
        "/setblock 20 171 25 minecraft:redstone_block",
        f"/tp {player} 20.5 171 28.5",
        f"/item replace entity {player} hotbar.0 with {LAMP}",
    ))
    multiplayer.until("the lamp to arrive", lambda: actor.call("inventory")["counts"].get(LAMP) == 1)
    actor.call("select", LAMP)
    actor.call("wait", 3)
    actor.call("interact", 20, 170, 26, "up")
    multiplayer.until("the lamp placed beside existing power", lambda: properties(actor, at) == {
        "powered": "true", "powering": "false", "activate": "false",
    })


def replay(host, actor, player, rows):
    place_next_to_source(host, actor, player)
    x, y, z = START
    host.command(f"/item replace entity {player} hotbar.0 with create:wrench")
    multiplayer.until("the survival Wrench to arrive",
                      lambda: actor.call("inventory")["counts"].get("create:wrench") == 1)
    actor.call("select", "create:wrench")
    start = host.clock()
    differences = []
    for row in rows:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        if tick in PULSES:
            lamp, on = PULSES[tick]
            block = "minecraft:redstone_block" if on else "minecraft:air"
            host.command(f"/setblock {x + lamp} {y} {z - 1} {block}")
        if tick in (28, 32):
            lane = 1 if tick == 28 else 0
            host.command(f"/tp {player} {x + lane + .5} {y} {z + 2.5}")
            actor.call("wait", 4)
            actor.call("interact", x + lane, y, z, "south")
            actor.call("wait", 4)
        parts = [row[side].split(":") for side in ("left", "middle", "right")]
        expected = [*[flags for flags, _ in parts], row["west_wire"], row["east_wire"]]
        if actor is not host or tick in (28, 32):
            multiplayer.until(f"the lamp cluster at Java tick {tick} to arrive",
                              lambda: sample(actor) == sample(host))
        observed = sample(host)
        if observed != expected:
            differences.append((tick, expected, observed))
        if observed == expected and tick in (31, 37):
            emission = int(parts[0][1])
            multiplayer.until(f"the lamp to settle at light {emission}", lambda: lighting(actor, emission))
    if differences:
        raise RuntimeError(f"Rose Quartz Lamp differed on {len(differences)} ticks. First {differences[:5]}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures" / "rose-quartz-lamp-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    x, y, z = START
    with fixture_world(args, "Rose Quartz Lamp", render=True, pack=args.pack) as host:
        host.commands((
            f"/fill {x-3} {y-1} {z-1} {x+5} {y-1} {z+4} minecraft:stone",
            f"/fill {x} {y} {z} {x+2} {y} {z} {LAMP}",
            f"/setblock {x-1} {y} {z} minecraft:comparator[facing=east]",
            f"/setblock {x+3} {y} {z} minecraft:comparator[facing=west]",
            f"/setblock {x-2} {y} {z} minecraft:redstone_wire",
            f"/setblock {x+4} {y} {z} minecraft:redstone_wire",
            "/fill 9 169 23 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-lamp-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="rose-quartz-lamp", pack=args.pack,
            ) as guest:
                multiplayer.until("the lamp guest to join", lambda: any(
                    p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]
                ))
                host.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} 12.5 171 24.5"))
                replay(host, guest, GUEST, rows)
        else:
            crafting.replay(host, {
                "recipe": "crafting/kinetics/rose_quartz_lamp", "width": "3",
                "slots": "create:polished_rose_quartz,minecraft:redstone,create:zinc_ingot",
                "output": LAMP, "count": "1", "remainder": "",
            })
            replay(host, host, "@s", rows)
    print(f"Matched all {len(rows)} Java Rose Quartz Lamp cluster and comparator ticks.")


if __name__ == "__main__":
    main()
