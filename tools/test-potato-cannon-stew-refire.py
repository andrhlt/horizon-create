#!/usr/bin/env python3
"""Compare real tick-paced empty-stew cannon refires with pinned Java."""
import argparse
import csv
import os
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

placement = import_module("test-package-placement")
filters, editor = placement.package.filters, placement.editor
AMMO = "minecraft:suspicious_stew"
CANNON = "create:potato_cannon"


def run(args):
    with (ROOT / "fixtures/potato-cannon-stew-refire-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    scenario = "StewRefireLan" if args.lan else "StewRefire"
    with TemporaryDirectory(prefix="hc-stew-refire-") as scratch:
        with fixture_world(args, scenario, render=True, pack=args.pack) as host:
            host.commands((
                "/fill 5 100 0 12 100 50 minecraft:stone",
                "/fill 5 101 0 12 106 50 minecraft:air",
            ))
            with filters.actor_for(host, args, Path(scratch) if args.lan else None) as (actor, name):
                host.commands((
                    f"/gamemode survival {name}",
                    f"/tp {name} 8.5 101 3.5 0 0",
                    f"/item replace entity {name} hotbar.0 with {CANNON}",
                    f"/item replace entity {name} hotbar.1 with {AMMO}",
                    f"/item replace entity {name} hotbar.2 with {AMMO}",
                ))
                actor.call("key", "1", "tap")

                def equipped():
                    inventory = actor.call("inventory")
                    return ((inventory["held"] or {}).get("item") == CANNON
                            and inventory["counts"].get(AMMO) == 2)

                editor.wait_for(actor, "cannon and ammo", equipped)
                actor.call("wait", 10)
                replies = actor.call("script", script="mouse right click\nwait 1\ninventory\n" * 45)
                inventories = [reply for reply in replies if "counts" in reply]
                first = next((i for i, inventory in enumerate(inventories)
                              if inventory["counts"].get(AMMO) == 1), None)
                assert first is not None and len(inventories) >= first + len(rows), (first, len(inventories))
                for tick, row in enumerate(rows):
                    assert int(row["tick"]) == tick, row
                    inventory = inventories[first + tick]
                    actual = (inventory["hotbar"][0].get("count", 0),
                              inventory["hotbar"][2].get("count", 0),
                              (inventory["held"] or {}).get("damage", 0))
                    expected = tuple(int(row[key]) for key in ("main_count", "remaining", "damage"))
                    assert actual == expected, (tick, actual, expected)
    print(f"Both empty-stew shots matched Java through tick {len(rows) - 1}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    os.environ["HORIZON_NO_AUDIO"] = "1"
    run(parser.parse_args())
