#!/usr/bin/env python3
"""Replay the two original Create depots feeding the same mechanical Display Board."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/items/depot_display.nbt")
BASE = (4, 98, -12)
DEPOTS = ((2, 1, 1), (1, 1, 1))
BOARDS = ((4, 2, 1), (5, 2, 1))
LEVERS = ((2, 4, 0), (1, 4, 0))
KEYS = ("front_depot", "rear_depot", "row_0", "row_1", "left_rpm", "right_rpm")


def pos(local):
    return " ".join(str(x + y) for x, y in zip(BASE, local, strict=True))


def sample(control):
    d0, d1, b0, b1 = control.commands(f"/data get block {pos(p)}" for p in (*DEPOTS, *BOARDS))
    depots = []
    for nbt in (d0, d1):
        inventory = re.search(r"\bItems: \[(.*?)\]", nbt)
        stack = re.search(r'id: "(?:[^:"]+):([^"]+)"', inventory[1]) if inventory else None
        depots.append(stack[1] if stack else "-")
    rows = []
    for i in range(2):
        row = re.search(rf'\bDisplay{i}: .*?\bText:.*?"text"\s*:\s*"([^"]*)"', b1.replace('\\\"', '"'))
        rows.append((row[1].lower().strip() if row else "") or "-")
    rates = [float(re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)f", block)[1]) for block in (b0, b1)]
    return (*depots, *rows, *rates)


def run(args):
    with (ROOT / "fixtures/depot_display-java.csv").open() as reference:
        expected = tuple(csv.DictReader(reference))
    with fixture_world(args, "Depot-display", STRUCTURE, render=args.visual) as control:
        control.commands((
            f"/place template create:{STRUCTURE.with_suffix('')} {' '.join(map(str, BASE))}",
            *(f"/data merge block {pos(p)} {{Speed:0.0f}}" for p in BOARDS),
            *(f"/setblock {pos(p)} minecraft:lever[face=wall,facing=north,powered=false]" for p in LEVERS),
        ))
        start = control.clock()
        path = ROOT / ".local/depot_display-horizon.csv"
        first_difference = None
        with path.open("w") as out:
            writer = csv.writer(out)
            writer.writerow(("tick", *KEYS))
            for row in expected:
                tick = int(row["tick"])
                if tick:
                    control.step_to(start + tick)
                found = sample(control)
                writer.writerow((tick, *found))
                wanted = tuple(row[key] for key in KEYS[:4]) + tuple(float(row[key]) for key in KEYS[4:])
                if found != wanted:
                    message = f"Tick {tick}: Horizon {found}, Java {wanted}"
                    if not args.diagnostics:
                        raise RuntimeError(message)
                    first_difference = first_difference or message
        if args.visual:
            control.command("/time set noon")
            control.command("/tp @s 8.5 101 -15.5")
            control.call("wait", 3)
            control.call("look-at", 8.9, 100.65, -10.7)
            control.call("key", "f1", "tap")
            control.call("wait", 4)
            control.call("screenshot", ROOT / ".local/depot-display.png")
        if first_difference:
            raise RuntimeError(first_difference)
    print(f"Both powered Display Board rows and depot items matched Java for all {len(expected)} ticks.")


def configure(args):
    with fixture_world(args, "Depot-display-settings", STRUCTURE, render=True) as control:
        control.commands((
            f"/place template create:{STRUCTURE.with_suffix('')} {' '.join(map(str, BASE))}",
            f"/setblock {pos((1, 1, 2))} minecraft:air",
            "/fill 2 98 -15 12 98 -13 minecraft:smooth_stone",
            "/fill 2 98 -12 2 98 -9 minecraft:smooth_stone",
            "/gamemode survival",
            "/tp @s 9.5 99 -13.5 0 -15",
            "/item replace entity @s hotbar.0 with create:display_link",
        ))
        control.call("wait", 3)
        control.call("key", "1", "tap")
        control.call("look-at", 9.5, 100.5, -10.99)
        control.call("mouse", "right", "click")
        control.call("wait", 3)
        items = control.command("/data get entity @s Inventory")
        if "create:click_to_link_data" not in items:
            raise RuntimeError(f"Display Board was not selected: {items}")
        control.command("/tp @s 2.5 99 -9.5 -90 20")
        control.call("wait", 3)
        control.call("interact", *map(int, pos((1, 1, 1)).split()), "south")
        control.call("wait", 3)
        attached = control.command(f"/data get block {pos((1, 1, 2))} TargetOffset")
        if "[I; 4, 1, -1]" not in attached:
            raise RuntimeError(f"Display link did not attach to the rear depot: {attached}")
        control.command(f"/item replace block {pos((1, 1, 1))} container.0 with minecraft:gold_ingot")
        for _ in range(4):
            control.step_to(control.clock() + 1)
        control.call("look-at", 5.1, 99.35, -9.5)
        control.call("wait", 3)
        control.call("mouse", "right", "click")
        control.call("wait", 5)
        control.call("click-button", "Next Row")
        control.call("wait", 3)
        control.call("click-button", "Combine Item Names")
        control.call("wait", 3)
        row = control.command(f"/data get block {pos((1, 1, 2))} TargetLine")
        values = sample(control)
        if not row.endswith("1") or values[3] != "gold ingot":
            raise RuntimeError(f"Row selection did not reach the Board: {row}, {values}")
        if args.visual:
            control.call("screenshot", ROOT / ".local/depot-display-settings.png")
    print("Survival Display Link settings sent a depot's item name to the second powered board row.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--configure", action="store_true")
    args = parser.parse_args()
    (configure if args.configure else run)(args)
