#!/usr/bin/env python3
"""Compare original Create bars' Stonecutter recipes, connections and waterlogging."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
MATERIALS = ("andesite", "brass", "copper")
GUEST = "MetalBarsGuest"
PROPERTIES = ("north", "east", "south", "west", "waterlogged")
DIRECTIONS = {
    2: (0, -1, "minecraft:stone"),
    3: (1, 0, "minecraft:iron_bars"),
    4: (0, 1, "minecraft:glass_pane"),
    5: (-1, 0, "minecraft:oak_fence"),
    6: (0, -1, "minecraft:air"),
    8: (1, 0, "minecraft:air"),
}


def read(kind):
    with (ROOT / f"fixtures/metal-bars-{kind}-java.csv").open(newline="") as source:
        return list(csv.DictReader(source))


def cut(control, row, slot):
    ingredient = row["ingredient"]
    control.command(f"/item replace entity @s hotbar.{slot} with {ingredient}")
    control.call("wait", 3)
    control.call("interact", 11, 171, 24, "up")
    control.call("click-slot", slot)
    control.call("click-slot", 600)
    multiplayer.until(f"the original {row['block']} recipe", lambda: row["recipe"] in
                      ((control.call("menu").get("info") or {}).get("recipes", [])))
    recipes = (control.call("menu").get("info") or {}).get("recipes", [])
    index = recipes.index(row["recipe"])
    if index >= 12:
        raise RuntimeError(f"The expected Stonecutter recipe is outside the first page at {index}.")
    widgets = control.call("ui")["widgets"]
    input_slot = next(node for node in widgets if node["id"] == "slot-600")
    left, top, _, _ = input_slot["bounds"]
    control.call("click-at", left + 40 + (index % 4) * 16, top - 10 + (index // 4) * 18)
    expected = int(row["count"])
    def result():
        return next((item["stack"] for item in control.call("menu")["slots"] if item["slot"] == 650), None)
    def ready():
        stack = result()
        return stack and (stack["item"], stack["count"]) == (row["block"], expected)
    multiplayer.until(f"the Stonecutter output for {row['block']}", ready)
    control.call("click-slot", 650, "shift")
    multiplayer.until(f"the {expected} {row['block']} to reach the inventory",
                      lambda: control.call("inventory")["counts"].get(row["block"]) == expected)
    control.call("close")
    control.call("wait", 3)
    actual = control.call("inventory")["counts"]
    if actual.get(row["block"]) != expected or actual.get(ingredient):
        raise RuntimeError(f"Stonecutting {ingredient} left {actual}.")


def check_neighbors(control, actor, player, position, rows):
    x, y, z = position
    material = rows[0]["material"]
    block = f"create:{material}_bars"
    control.command(f"/tp {player} {x + 0.5} {y} {z + 2.5}")
    actor.call("wait", 5)
    actor.call("select", block)
    actor.call("interact", x, y - 1, z, "up")
    multiplayer.until(f"{block} to be placed", lambda: control.call("block", *position)["block"] == block)
    for row in rows:
        tick = int(row["tick"])
        if tick in DIRECTIONS:
            dx, dz, neighbor = DIRECTIONS[tick]
            control.command(f"/setblock {x + dx} {y} {z + dz} {neighbor}")
        if tick == 7:
            control.command(f"/item replace entity {player} hotbar.8 with minecraft:water_bucket")
            multiplayer.until("the water bucket to reach the player", lambda: actor.call("inventory")["counts"].get("minecraft:water_bucket"))
            actor.call("select", "minecraft:water_bucket")
            actor.call("interact", x, y, z, "up")
        control.step_to(control.clock() + 1)
        actual = control.call("block", *position)
        fields = dict(re.findall(r"(\w+)=(\w+)", actual["state"]))
        if actual["block"] != block or any(fields.get(name) != row[name] for name in PROPERTIES):
            raise RuntimeError(f"Java {row}. Host {actual}.")
        multiplayer.until(f"the guest to see Java's {material} bars state at tick {tick}",
                          lambda: actor.call("block", *position)["state"] == actual["state"])



def exercise_lan(args, host, recipes, states):
    port = host.call("lan", "open", "0", "commands", "force")["port"]
    with TemporaryDirectory(prefix="hc-metal-bars-lan-") as scratch, multiplayer.joined_client(
        args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
        scenario="metal-bars", pack=args.pack,
    ) as guest:
        multiplayer.until("a connected guest", lambda: any(
            user["name"] == GUEST and user["placed"] for user in host.call("lan", "status")["guests"]
        ))
        host.command(f"/gamemode survival {GUEST}")
        host.commands(f"/item replace entity {GUEST} hotbar.{index} with {row['block']} 4"
                      for index, row in enumerate(recipes))
        multiplayer.until("the three bars items", lambda: all(
            guest.call("inventory")["counts"].get(row["block"], 0) == 4 for row in recipes
        ))
        for index, material in enumerate(MATERIALS):
            check_neighbors(host, guest, GUEST, (7 + 5 * index, 171, 21),
                            [row for row in states if row["material"] == material])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    recipes, states = read("recipe"), read("state")
    with fixture_world(args, "Metal-bars", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 5 170 19 22 170 29 minecraft:stone",
            "/setblock 11 171 24 minecraft:stonecutter",
            "/tp @s 11.5 171 26.5",
            "/gamemode survival",
        ))
        if args.lan:
            exercise_lan(args, control, recipes, states)
        else:
            for slot, recipe in enumerate(recipes):
                cut(control, recipe, slot)
            for i, material in enumerate(MATERIALS):
                check_neighbors(control, control, "@s", (7 + 5 * i, 171, 21),
                                [row for row in states if row["material"] == material])
    print("All 24 connection and waterlogging states match Java." if args.lan else
          "All three Stonecutter recipes and 24 connection and waterlogging states match Java.")


if __name__ == "__main__":
    main()
