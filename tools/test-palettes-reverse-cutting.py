#!/usr/bin/env python3
"""Stonecut the seven vanilla originals from a Create cut-stone block."""
import argparse
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

palettes = import_module("test-stone-palettes")


def run(args):
    with (ROOT / "fixtures/palette-reverse-cutting-java.csv").open(newline="") as stream:
        original = list(csv.DictReader(stream))
    env = {"HORIZON_NO_AUDIO": "1"}
    with fixture_world(args, "PaletteReverseCutting", render=True, pack=args.pack, env=env) as world:
        world.commands((
            "/fill 3 96 -11 12 96 -6 minecraft:smooth_stone",
            "/setblock 5 97 -9 minecraft:stonecutter",
            "/tp @s 3.0 97.0 -8.5 -90 20",
            "/gamemode survival",
        ))
        for slot, row in enumerate(original):
            world.command(f"/item replace entity @s hotbar.{slot} with {row['ingredient']}")
        world.call("interact", 5, 97, -9, "up")
        palettes.wait_for("Stonecutter", lambda: world.call("menu").get("station"), lambda name: name == "Stonecutter")
        for slot, row in enumerate(original):
            output, count = row["output"], int(row["count"])
            world.call("click-slot", slot)
            world.call("click-slot", 600)
            palettes.selection(world, row["recipe"], None)

            def result():
                return next(entry["stack"] for entry in world.call("menu")["slots"] if entry["slot"] == 650)

            palettes.wait_for(output, result, lambda stack: stack and (stack["item"], stack["count"]) == (output, count))
            world.call("click-slot", 650, "shift")
            palettes.wait_for(output + " in inventory", lambda: world.call("inventory")["counts"],
                              lambda inventory: inventory.get(output) == count and row["ingredient"] not in inventory)
    print(f"All {len(original)} original reverse Stonecutter recipes passed in survival.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
