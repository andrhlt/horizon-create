#!/usr/bin/env python3
"""Compare window glass recycling and Silk Touch with the pinned Java fixtures."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

FRAMED = ("tiled_glass", "framed_glass", "horizontal_framed_glass", "vertical_framed_glass")
RIGS = tuple(family + suffix for family in FRAMED for suffix in ("", "_pane"))
FIELDS = ("tick", "block", "cook", "total", "burn", "lit", "input_count", "output", "output_count")
PICKAXE = "minecraft:diamond_pickaxe"


def reference(name):
    with (ROOT / f"fixtures/window-{name}-java.csv").open() as source:
        return list(csv.DictReader(source))


def coords(position):
    return " ".join(map(str, position))


def numeric(nbt, name):
    match = re.search(rf'\b{name}: (-?\d+)', nbt)
    if match is None:
        raise RuntimeError(f"Missing {name} in {nbt}")
    return match[1]


def read_furnace(tick, name, nbt, lit):
    slots = {}
    for match in re.finditer(r'\{[^{}]*\}', nbt):
        stack = match[0]
        if "Slot:" not in stack:
            continue
        item = re.search(r'\bid: "([^"]+)"', stack)
        if item:
            slots[numeric(stack, "Slot")] = (item[1], numeric(stack, "count"))
    output_id, output_count = slots.get("2", ("minecraft:air", "0"))
    return (
        str(tick), name,
        *(numeric(nbt, key) for key in ("cooking_time_spent", "cooking_total_time", "lit_time_remaining")),
        "true" if lit.startswith("Test passed") else "false",
        slots.get("0", ("minecraft:air", "0"))[1], output_id, output_count,
    )


def recycling(args):
    expected = reference("furnaces")
    positions = {name: (5 + (i % 4) * 2, 180, 23 + (i // 4) * 2) for i, name in enumerate(RIGS)}
    trace = ROOT / ".local/window-furnaces-horizon.csv"
    commands = tuple(operation for at in positions.values() for operation in (
        f"/data get block {coords(at)}",
        f"/execute if block {coords(at)} minecraft:furnace[lit=true]",
    ))
    with fixture_world(args, "Window-recycling", pack=args.pack) as control, trace.open("w", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(FIELDS)
        control.commands((
            "/tp @s 8.5 180 22.5",
            *(command for name, at in positions.items() for command in (
                f"/setblock {coords(at)} minecraft:furnace",
                f"/item replace block {coords(at)} container.0 with create:{name}",
                f"/item replace block {coords(at)} container.1 with minecraft:coal",
            )),
        ))
        starting_tick = control.clock()
        for tick in range(53):
            if tick:
                control.step_to(starting_tick + tick)
            observed = control.commands(commands)
            for index, name in enumerate(positions):
                actual = read_furnace(tick, name, *observed[index * 2:index * 2 + 2])
                wanted = tuple(expected[tick * len(positions) + index][field] for field in FIELDS)
                writer.writerow(actual)
                if actual != wanted:
                    raise RuntimeError(f"Furnace row differs. Java {wanted}, Horizon {actual}.")
    print(f"All {len(expected)} Java furnace samples matched across eight glass recycling recipes.")


def break_windows(args):
    selected = {"create:framed_glass", "create:oak_window_pane", "create:weathered_iron_window_pane"}
    rows = [row for row in reference("loot") if f"create:{row['block']}" in selected]
    target = (8, 180, 23)
    drops = "@e[type=minecraft:item,x=4,y=179,z=21,dx=8,dy=5,dz=5]"
    with fixture_world(args, "Window-silk-touch", pack=args.pack, render=True) as control:
        control.commands((
            "/fill 5 179 21 11 179 25 minecraft:smooth_stone",
            "/fill 5 180 21 11 183 25 minecraft:air",
            "/tp @s 6.5 180 23.5",
            "/gamemode survival",
        ))
        for row in rows:
            control.commands((
                f"/kill {drops}",
                f"/setblock {coords(target)} create:{row['block']}",
                f"/item replace entity @s hotbar.0 with {PICKAXE}",
            ))
            control.call("wait", 2)
            control.call("select", PICKAXE)
            if row["silk"] == "true":
                enchanted = control.command("/enchant @s minecraft:silk_touch 1")
                if not enchanted.startswith("Applied enchantment Silk Touch"):
                    raise RuntimeError(enchanted)
            control.call("look-at", 8.5, 180.5, 23.5)
            control.call("mouse", "left", "down")
            try:
                for _ in range(20):
                    if control.call("block", *target)["block"] == "minecraft:air":
                        break
                    control.step_to(control.clock() + 1)
                else:
                    raise RuntimeError(f"Player could not mine {row['block']}.")
            finally:
                control.call("mouse", "left", "up")
            control.call("wait", 3)
            found = control.command(f"/execute if entity {drops}").startswith("Test passed")
            actual = ""
            if found:
                nbt = control.command(f"/data get entity {drops[:-1]},limit=1] Item")
                item = re.search(r'\bid: "([^"]+)"', nbt)
                if item is None:
                    raise RuntimeError(nbt)
                actual = f"{item[1]}={numeric(nbt, 'count')}"
            if actual != row["drops"]:
                raise RuntimeError(f"Java {row} but Horizon yielded {actual!r}.")
    print(f"All {len(rows)} plain and Silk Touch breaks matched their Java loot outcomes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--loot", action="store_true")
    args = parser.parse_args()
    (break_windows if args.loot else recycling)(args)
