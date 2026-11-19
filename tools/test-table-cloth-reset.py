#!/usr/bin/env python3
"""Clear a named stack of every Table Cloth material in survival."""
import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world
from table_cloths import TABLE_CLOTHS

crafting = import_module("test-survival-crafting")
mp = import_module("test-multiplayer")


def run(args):
    env = {"HORIZON_NO_AUDIO": "1"}
    with fixture_world(args, "TableClothReset", render=True, pack=args.pack, env=env) as world:
        world.command("/gamemode survival")
        for name in TABLE_CLOTHS:
            item = f"create:{name}"
            recipe = f"create:crafting/logistics/{name}_clear"
            give = world.command(f"/recipe give @s {recipe}")
            assert "unknown recipe" not in give.lower(), give
            world.commands((
                "/clear @s",
                f'/item replace entity @s hotbar.0 with {item}[minecraft:custom_name="To Clear"]',
            ))
            held = world.command("/data get entity @s Inventory")
            assert 'To Clear' in held, held
            world.call("open-inventory")
            crafting.distribute(world, 0, (100,))
            crafting.craft(world, item, 1)
            world.call("close")
            inventory = world.call("inventory")["counts"]
            assert inventory.get(item) == 1, inventory
            def reset():
                data = world.command("/data get entity @s Inventory")
                return 'To Clear' not in data and f'id: "{item}"' in data

            mp.until(f"{item} reset to reach the server inventory", reset)
    print(f"All {len(TABLE_CLOTHS)} original Table Cloth reset recipes removed the custom name in survival.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
