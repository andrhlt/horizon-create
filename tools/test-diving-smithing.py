#!/usr/bin/env python3
"""Take the six original Netherite diving upgrades in a survival Smithing Table."""
import argparse
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")


def replay(world, row):
    recipe = f"create:{row['recipe']}"
    output = row["output"]
    give = world.command(f"/recipe give @s {recipe}")
    assert "unknown recipe" not in give.lower(), give
    world.commands((
        "/clear @s",
        f"/item replace entity @s hotbar.0 with {row['template']}",
        f'/item replace entity @s hotbar.1 with {row["base"]}[minecraft:custom_name="Dive Trace"]',
        f"/item replace entity @s hotbar.2 with {row['addition']}",
    ))
    world.call("wait", 3)
    world.call("interact", 5, 97, -9, "up")
    mp.until("the Smithing Table to open", lambda: world.call("menu").get("station") == "Smithing")
    for slot in range(3):
        world.call("click-slot", slot)
        world.call("click-slot", 600 + slot)

    def ready():
        slot = next((slot for slot in world.call("menu")["slots"] if slot["slot"] == 650), {})
        result = slot.get("stack")
        return result and (result["item"], result["count"]) == (output, 1)

    mp.until(f"{row['recipe']} output", ready)
    world.call("click-slot", 650, "shift")
    world.call("close")
    mp.until("the upgrade to reach the player", lambda: world.call("inventory")["counts"] == {output: 1})

    def check_name():
        inventory = world.command("/data get entity @s Inventory")
        return 'Dive Trace' in inventory and f'id: "{output}"' in inventory

    mp.until("the upgraded item to retain the base name", check_name)
    print(f"{recipe} produced {output} and retained the base name.", flush=True)


def run(args):
    with (ROOT / "fixtures/diving-smithing-java.csv").open(newline="") as stream:
        recipes = list(csv.DictReader(stream))
    env = {"HORIZON_NO_AUDIO": "1"}
    with fixture_world(args, "DivingSmithing", render=True, pack=args.pack, env=env) as world:
        world.commands((
            "/fill 3 96 -11 12 96 -6 minecraft:smooth_stone",
            "/setblock 5 97 -9 minecraft:smithing_table",
            "/tp @s 3.0 97.0 -8.5 -90 20",
            "/gamemode survival",
        ))
        for row in recipes:
            replay(world, row)
    print(f"All {len(recipes)} original diving upgrades passed in survival.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
