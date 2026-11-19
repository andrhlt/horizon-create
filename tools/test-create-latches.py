#!/usr/bin/env python3
"""Compare original Create's two latches using pulse and manual inputs."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

crafting = import_module("test-machine-crafting")
multiplayer = import_module("test-multiplayer")
GUEST = "LatchGuest"
TOGGLE = "create:powered_toggle_latch"
LATCH = "create:powered_latch"
CASES = ((TOGGLE, 19), (LATCH, 25))
FIELDS = ("toggle_rear", "toggle_output", "toggle_wire", "latch_rear", "latch_side", "latch_output", "latch_wire")


def props(actor, x, y, z):
    state = actor.call("block", x, y, z)["state"]
    return dict(re.findall(r"(\w+)=(\w+)", state))


def sample(actor):
    observed = []
    for block, depth in CASES:
        latch = props(actor, 9, 171, depth)
        names = ("powered", "powered_side", "powering") if block == LATCH else ("powered", "powering")
        observed.extend(latch.get(name) for name in names)
        observed.append(props(actor, 8, 171, depth).get("power"))
    return observed


def pulse(host, tick):
    if tick in (3, 7, 10, 19, 35):
        source = "minecraft:redstone_block" if tick in (3, 10, 35) else "minecraft:air"
        host.commands(f"/setblock 10 171 {depth} {source}" for _, depth in CASES)
        if tick == 35:
            host.commands(f"/setblock 10 171 {depth} minecraft:air" for _, depth in CASES)
    if tick in (12, 16, 22, 26):
        source = "minecraft:redstone_block" if tick in (12, 22) else "minecraft:air"
        host.command(f"/setblock 9 171 26 {source}")


def press(host, actor, who, tick):
    for _, depth in CASES:
        stance = [9.5, 171.0, depth - 1.5]
        host.command(f"/tp {who} {' '.join(map(str, stance))}")
        multiplayer.until("the player to reach the latch",
                          lambda: actor.call("state")["player"]["position"] == stance)
        sneaking = tick == 32
        if sneaking:
            actor.call("key", "shift", "down")
            actor.call("wait", 3)
        try:
            actor.call("look-at", 9.5, 171.10, depth + .5)
            multiplayer.until(f"the latch to be targeted at Java tick {tick}", lambda:
                              (actor.call("looking-at").get("block") or {}).get("pos") == [9, 171, depth])
            actor.call("mouse", "right", "click")
            actor.call("wait", 3)
        finally:
            if sneaking:
                actor.call("key", "shift", "up")
                actor.call("wait", 3)


def replay(host, actor, who, expected):
    host.command(f"/clear {who}")
    host.commands(
        f"/setblock 9 171 {depth} {block}[facing=east]" for block, depth in CASES
    )
    host.commands(f"/setblock 8 171 {depth} minecraft:redstone_wire" for _, depth in CASES)
    start = host.clock()
    differences = []
    for row in expected:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        pulse(host, tick)
        if tick in (14, 24, 28, 32):
            press(host, actor, who, tick)
        observation = sample(host)
        value = [row[field] for field in FIELDS]
        if value != observation:
            differences.append((tick, value, observation))
        if actor is not host:
            multiplayer.until(f"both latch states from tick {tick} to arrive", lambda: sample(actor) == observation)
    if differences:
        raise RuntimeError(f"Latches differed on {len(differences)} ticks. First {differences[:5]}.")


def recipe_inputs():
    for block in (TOGGLE, LATCH):
        dust = "minecraft:redstone" if block == LATCH else "_"
        cells = ["_", "minecraft:redstone_torch", "_", dust, "minecraft:lever", dust]
        cells.extend(["minecraft:stone"] * 3)
        yield {"recipe": f"crafting/logistics/{block.removeprefix('create:')}", "width": "3",
               "slots": ",".join(cells), "output": block, "count": "1", "remainder": ""}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures" / "create-latches-java.csv").open() as source:
        expected = list(csv.DictReader(source))
    with fixture_world(args, "Create latches", render=not args.lan, pack=args.pack) as host:
        host.commands((
            "/fill 6 170 15 12 170 27 minecraft:stone",
            "/fill 10 169 23 15 169 27 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-latches-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, scenario="create-latches", pack=args.pack,
            ) as guest:
                multiplayer.until("the latch guest to join", lambda: any(
                    player["name"] == GUEST and player["placed"]
                    for player in host.call("lan", "status")["guests"]
                ))
                host.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} 9.5 171 17.5"))
                replay(host, guest, GUEST, expected)
        else:
            for recipe in recipe_inputs():
                crafting.replay(host, recipe)
            replay(host, host, "@s", expected)
    print(f"Both Create latch states and physical wire outputs matched {len(expected)} Java ticks.")


if __name__ == "__main__":
    main()
