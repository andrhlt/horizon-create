#!/usr/bin/env python3
"""Compare Zinc mining drops and heating recipes with pinned Java Create."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
import time

from fixture_world import ROOT, fixture_world

recycling = import_module("test-window-recycling")
coords = recycling.coords


def reference(name):
    with (ROOT / f"fixtures/zinc-{name}-java.csv").open(newline="") as source:
        return list(csv.DictReader(source))


def mine(args, rows):
    target = (8, 180, 23)
    item = "@e[type=minecraft:item,x=4,y=179,z=21,dx=8,dy=5,dz=5]"
    with fixture_world(args, "Zinc-mining", pack=args.pack, render=True) as control:
        control.commands((
            "/fill 5 179 21 11 179 25 minecraft:smooth_stone",
            "/fill 5 180 21 11 183 25 minecraft:air",
            "/tp @s 6.5 180 23.5",
            "/gamemode survival",
        ))
        for row in rows:
            name = row["block"]
            material = "stone" if row["tool"] == "stone" else "iron"
            tool = f"minecraft:{material}_pickaxe"
            control.commands((
                f"/kill {item}",
                f"/setblock {coords(target)} create:{name}",
                f"/item replace entity @s hotbar.0 with {tool}",
            ))
            control.call("wait", 2)
            control.call("select", tool)
            if row["tool"] == "silk":
                enchanted = control.command("/enchant @s minecraft:silk_touch 1")
                if not enchanted.startswith("Applied enchantment Silk Touch"):
                    raise RuntimeError(enchanted)
            control.call("look-at", 8.5, 180.5, 23.5)
            control.call("mouse", "left", "down")
            try:
                for _ in range(130):
                    if control.call("block", *target)["block"] == "minecraft:air":
                        break
                    control.step_to(control.clock() + 1)
                else:
                    raise RuntimeError(f"The player could not mine {name} using {tool}.")
            finally:
                control.call("mouse", "left", "up")
            control.call("wait", 3)
            actual = ("_", "0")
            if control.command(f"/execute if entity {item}").startswith("Test passed"):
                nbt = control.command(f"/data get entity {item[:-1]},limit=1] Item")
                identifier = re.search(r'\bid: "([^"]+)"', nbt)
                if identifier is None:
                    raise RuntimeError(nbt)
                actual = (identifier[1], recycling.numeric(nbt, "count"))
            expected = (row["drop"], row["count"])
            if actual != expected:
                raise RuntimeError(f"{name} with {row['tool']} yielded {actual}, Java yielded {expected}.")
    print(f"All {len(rows)} survival mining cases matched Java's Zinc drops.")


def step(control, ticks):
    goal = control.clock() + ticks
    control.command(f"/tick step {ticks}")
    deadline = time.monotonic() + 12
    while (now := control.clock()) != goal:
        if now > goal or time.monotonic() >= deadline:
            raise RuntimeError(f"Expected tick {goal}, reached {now}.")
        time.sleep(0.03)


def heat(args, rows, *, world="Zinc-heating"):
    positions = [(5 + index % 4 * 2, 180, 23 + index // 4 * 2) for index in range(len(rows))]
    heaters = ["minecraft:furnace" if row["type"] == "minecraft:smelting" else "minecraft:blast_furnace"
               for row in rows]
    last = 0
    with fixture_world(args, world, pack=args.pack) as control:
        control.command("/tp @s 8.5 180 22.5")
        control.commands(command for position, heater, row in zip(positions, heaters, rows, strict=True)
                         for command in (
                             f"/setblock {coords(position)} {heater}",
                             f"/item replace block {coords(position)} container.0 with create:{row['input']}",
                             f"/item replace block {coords(position)} container.1 with minecraft:coal",
                         ))
        queries = [command for position, heater in zip(positions, heaters, strict=True) for command in (
            f"/data get block {coords(position)}",
            f"/execute if block {coords(position)} {heater}[lit=true]",
        )]
        for tick in (1, 99, 100, 199, 200):
            step(control, tick - last)
            last = tick
            readings = control.commands(queries)
            for index, row in enumerate(rows):
                reading = recycling.read_furnace(tick, row["input"], *readings[index * 2:index * 2 + 2])
                elapsed, duration = map(int, reading[2:4])
                count = int(reading[-1])
                expected_duration = int(row["duration"])
                if tick < expected_duration:
                    valid = (elapsed, duration, count) == (tick, expected_duration, 0)
                else:
                    valid = (reading[-2], count) == (row["output"], int(row["count"]))
                if not valid:
                    raise RuntimeError(f"Tick {tick}, Java {row}, Horizon {reading}")
    print(f"All {len(rows)} cooking inputs matched Java at the completion ticks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--heating", action="store_true")
    mode.add_argument("--crushed", action="store_true")
    args = parser.parse_args()
    if args.crushed:
        with (ROOT / "fixtures/crushed-materials-heating-java.csv").open(newline="") as source:
            heat(args, list(csv.DictReader(source)), world="Crushed-materials-heating")
    elif args.heating:
        heat(args, reference("heating"))
    else:
        mine(args, reference("harvest"))


if __name__ == "__main__":
    main()
