#!/usr/bin/env python3
"""Compare real repeated potato cannon clicks against the pinned Java cooldown."""
import argparse
import csv
from importlib import import_module
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

placement = import_module("test-package-placement")
filters, editor = placement.package.filters, placement.editor


def run(args):
    with (ROOT / "fixtures/potato-cannon-cooldown-java.csv").open() as f:
        java = {int(row["tick"]): row for row in csv.DictReader(f)}
    with TemporaryDirectory(prefix="hc-potato-cooldown-") as tmp:
        with fixture_world(args, "PotatoCooldown", render=True, pack=args.pack) as host:
            host.commands(("/fill 5 100 0 12 100 50 minecraft:stone", "/fill 5 101 0 12 106 50 minecraft:air"))
            with filters.actor_for(host, args, Path(tmp) if args.lan else None) as (actor, name):
                host.commands((f"/gamemode survival {name}", f"/clear {name}",
                    f"/tp {name} 8.5 101 3.5 0 0",
                    f"/item replace entity {name} hotbar.0 with create:potato_cannon",
                    f"/item replace entity {name} hotbar.1 with minecraft:potato 3"))
                actor.call("key", "1", "tap")
                editor.wait_for(actor, "cannon and ammunition", lambda:
                    (actor.call("inventory")["held"] or {}).get("item") == "create:potato_cannon"
                    and actor.call("inventory")["counts"].get("minecraft:potato") == 3)
                editor.wait_for(actor, "launch position", lambda: tuple(actor.call("state")["player"]["position"][:3]) == (8.5,101,3.5))
                actor.call("wait", 10)
                script = "mouse right click\nwait 1\ninventory\n" * 20
                replies = actor.call("script", script=script)
                inventories = [reply for reply in replies if "counts" in reply]
                first = next(i for i, inv in enumerate(inventories) if inv["counts"].get("minecraft:potato") == 2)
                assert len(inventories) >= first + 17, (first, len(inventories))
                for tick in range(17):
                    inv = inventories[first + tick]
                    actual = (inv["counts"].get("minecraft:potato", 0), (inv["held"] or {}).get("damage", 0))
                    expected = (int(java[tick]["ammo"]), int(java[tick]["damage"]))
                    assert actual == expected, (tick, actual, expected)
                print("Repeated clicks matched Java: ticks 1–14 blocked, tick 15 fired, and tick 16 was cooling.")



if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        p.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    p.add_argument("--lan", action="store_true")
    os.environ["HORIZON_NO_AUDIO"] = "1"
    run(p.parse_args())
