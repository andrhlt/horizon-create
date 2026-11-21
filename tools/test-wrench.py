#!/usr/bin/env python3
"""Replay six real Java Wrench targets using a player in Horizon survival."""

import argparse
import csv
import math
from pathlib import Path

from fixture_world import ROOT, fixture_world

POSITION = (8, 180, 23)
START = (
    "create:shaft[axis=y]",
    "create:cogwheel[axis=y]",
    "create:gearbox[axis=y]",
    "create:creative_motor[facing=north]",
    "create:encased_fan[facing=north]",
    "create:item_drain",
)
APPROACH = {
    "down": (8.3, 177.0, 23.5),
    "up": (9.5, 182.0, 23.5),
    "north": (8.5, 179.0, 21.5),
    "south": (8.5, 179.0, 25.5),
    "west": (6.5, 179.0, 23.5),
    "east": (10.5, 179.0, 23.5),
}


def sneak_click(control, aim):
    target = tuple(math.floor(value) for value in aim)
    control.call("key", "shift", "down")
    control.call("wait", 4)
    try:
        control.call("look-at", *aim)
        control.call("wait", 1)
        looking = control.call("looking-at")
        hit = looking.get("block") or {}
        if looking.get("kind") != "block" or hit.get("pos") != list(target):
            raise RuntimeError(f"Wrench pickup aim missed {target}: {looking}")
        control.call("mouse", "right", "click")
        control.call("wait", 3)
    finally:
        control.call("key", "shift", "up")


def state(value):
    ident, bracket, properties = value.partition("[")
    return ident, dict(entry.split("=", 1) for entry in properties.rstrip("]").split(",") if entry) if bracket else {}


def observe(control, row):
    expected_block, expected_properties = state(row["state"])
    visible = control.call("block", *POSITION)["state"]
    actual_block, actual_properties = state(visible)
    pose = {key: value for key, value in expected_properties.items() if key in {"axis", "facing"}}
    if actual_block != expected_block or any(actual_properties.get(k) != v for k, v in pose.items()):
        raise RuntimeError(f"Rig {row['rig']} action {row['action']}: Java {row['state']}, Horizon {visible}")
    contents = control.call("inventory")["counts"]
    expected = dict(entry.split("=", 1) for entry in row["inventory"].split("|") if entry)
    actual = {ident: count for ident, count in contents.items() if ident != "create:wrench"}
    if actual != {ident: int(count) for ident, count in expected.items()} or contents.get("create:wrench") != 1:
        raise RuntimeError(f"Rig {row['rig']} action {row['action']}: Java inventory {expected}, Horizon {contents}")
    return visible, "|".join(f"{item}={count}" for item, count in sorted(actual.items()))


def run(args):
    with (ROOT / "fixtures/wrench-java.csv").open() as text:
        expected = list(csv.DictReader(text))
    with fixture_world(args, "Wrench", render=True, pack=args.pack) as control:
        control.commands((
            "/setblock 8 176 23 minecraft:smooth_stone",
            "/setblock 9 181 23 minecraft:smooth_stone",
            "/setblock 8 178 21 minecraft:smooth_stone",
            "/setblock 8 178 25 minecraft:smooth_stone",
            "/setblock 6 178 23 minecraft:smooth_stone",
            "/setblock 10 178 23 minecraft:smooth_stone",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:wrench",
        ))
        control.call("select", "create:wrench")
        path = ROOT / ".local/wrench-horizon.csv"
        with path.open("w", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(("rig", "action", "face", "state", "inventory"))
            for row in expected:
                rig, action, face = int(row["rig"]), int(row["action"]), row["face"]
                if action == 0:
                    control.command(f"/setblock 8 180 23 {START[rig]}")
                x, y, z = APPROACH[face]
                control.command(f"/tp @s {x} {y} {z}")
                control.call("wait", 3)
                if action == 6:
                    sneak_click(control, (8.5, 180.5, 23.5))
                else:
                    control.call("interact", *POSITION, face)
                control.call("wait", 3)
                writer.writerow((rig, action, face, *observe(control, row)))
    print(f"Wrench rotations and survival pickup matched all {len(expected)} original Java actions.")


def run_tagged(args):
    targets = (
        ("minecraft:rail", (8.5, 180.06, 23.5)),
        ("minecraft:repeater", (8.5, 180.07, 23.5)),
        ("minecraft:redstone_wall_torch[facing=east]", (8.35, 180.4, 23.5)),
        ("minecraft:hopper", (8.5, 180.75, 23.5)),
        ("minecraft:stone", (8.5, 180.5, 23.5)),
    )
    with (ROOT / "fixtures/wrench-tagged-java.csv").open() as text:
        expected = list(csv.DictReader(text))
    with fixture_world(args, "Wrench-tagged", render=True, pack=args.pack) as control:
        control.commands((
            "/setblock 8 179 23 minecraft:smooth_stone",
            "/setblock 7 180 23 minecraft:smooth_stone",
            "/setblock 10 178 23 minecraft:smooth_stone",
            "/tp @s 10.5 179 23.5",
            "/gamemode survival",
        ))
        for row, (block, aim) in zip(expected, targets, strict=True):
            control.commands((
                "/setblock 8 180 23 minecraft:air",
                f"/setblock 8 180 23 {block}",
                "/clear @s",
                "/item replace entity @s hotbar.0 with create:wrench",
            ))
            control.call("wait", 3)
            control.call("select", "create:wrench")
            sneak_click(control, aim)
            control.call("wait", 3)
            observe(control, row | {"action": "crouch pickup"})
    print(f"Wrench tagged pickup matched all {len(targets)} original Java cases and their inventory items.")


def run_crafting(args):
    table = (9, 95, -9)
    inputs = (
        ("create:golden_sheet", 3, (100, 101, 103)),
        ("create:cogwheel", 1, (104,)),
        ("minecraft:stick", 1, (107,)),
    )
    with fixture_world(args, "Wrench-crafting", render=True, pack=args.pack) as control:
        control.commands((
            "/gamemode survival",
            f"/setblock {' '.join(map(str, table))} minecraft:crafting_table",
            "/tp @s 7.5 95 -9.5",
            *(f"/item replace entity @s hotbar.{index} with {item} {count}"
              for index, (item, count, _) in enumerate(inputs)),
        ))
        control.call("wait", 3)
        control.call("interact", *table, "west")
        for item, _, slots in inputs:
            inventory = control.call("inventory")
            carried = [*inventory["hotbar"], *inventory["main"]]
            source = next(entry["slot"] for entry in carried if entry.get("item") == item)
            control.call("click-slot", source)
            for slot in slots:
                control.call("click-slot", slot, "right")
        menu = control.call("menu")
        result_slot = next((entry for entry in menu["slots"] if entry["slot"] == 200), None)
        if result_slot is None:
            raise RuntimeError(f"Crafting table did not expose its result slot: {menu}")
        result = result_slot["stack"]
        if (result["item"], result["count"]) != ("create:wrench", 1):
            raise RuntimeError(f"Expected the Java Wrench recipe result, got {result}")
        control.call("click-slot", 200, "shift")
        counts = control.call("inventory")["counts"]
        expected = {"create:wrench": 1}
        if counts != expected:
            raise RuntimeError(f"Wrench crafting inventory: expected {expected}, got {counts}")
    print("Survival crafting consumed the three golden sheets, Cogwheel and Stick for one Wrench.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--tagged", action="store_true")
    parser.add_argument("--craft", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    (run_crafting if args.craft else run_tagged if args.tagged else run)(args)
