#!/usr/bin/env python3
"""Compare real tick-paced shots against the six-ammo Java cooldown batch."""
import argparse
import csv
from importlib import import_module
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

placement = import_module("test-package-placement")
filters, editor = placement.package.filters, placement.editor
CASES = ("potato", "carrot", "apple", "beetroot", "melon_slice", "golden_carrot")


def run(args):
    with (ROOT / "fixtures/potato-cannon-batch-cooldown-java.csv").open() as f:
        rows = {(r["case"], int(r["tick"])): r for r in csv.DictReader(f)}
    cases = args.case or CASES
    with TemporaryDirectory(prefix="hc-ammo-cooldown-") as tmp:
        with fixture_world(args, "AmmoCooldown", render=True, pack=args.pack) as host:
            host.commands(("/fill 5 100 0 12 100 50 minecraft:stone", "/fill 5 101 0 12 106 50 minecraft:air"))
            with filters.actor_for(host, args, Path(tmp) if args.lan else None) as (actor, name):
                host.command(f"/gamemode survival {name}")
                for index, case in enumerate(cases):
                    if index: actor.call("wait", 20)
                    host.call("command", f"/clear {name}")
                    host.command(f"/tp {name} 8.5 101 3.5 0 0")
                    host.command(f"/item replace entity {name} hotbar.0 with create:potato_cannon")
                    host.command(f"/item replace entity {name} hotbar.1 with minecraft:{case} 3")
                    actor.call("key", "1", "tap")
                    ammo = f"minecraft:{case}"
                    editor.wait_for(actor,"cannon and ammo",lambda:
                        (actor.call("inventory")["held"] or {}).get("item") == "create:potato_cannon"
                        and actor.call("inventory")["counts"].get(ammo) == 3)
                    actor.call("wait",10)
                    reload = next(t for t in range(1,17) if rows[(case,t)]["cooling"] == "false")
                    replies = actor.call("script", script="mouse right click\nwait 1\ninventory\n" * (reload + 5))
                    inventories = [reply for reply in replies if "counts" in reply]
                    first = next(i for i, inv in enumerate(inventories) if inv["counts"].get(ammo) == 2)
                    assert len(inventories) >= first + reload + 2, (case, first, len(inventories))
                    for tick in range(reload + 2):
                        inv = inventories[first + tick]
                        actual = (inv["counts"].get(ammo,0), (inv["held"] or {}).get("damage",0))
                        row = rows[(case,tick)]
                        expected = (int(row["ammo"]),int(row["damage"]))
                        assert actual == expected, (case,tick,actual,expected)
                    print(f"{case}: cooldown {reload} ticks matched Java", flush=True)
    print("Six ammunition cooldown boundaries matched Java.")


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("ctl","client","resources"):
        p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
    p.add_argument("--pack",type=Path,default=ROOT/".local/create.hmod")
    p.add_argument("--lan",action="store_true")
    p.add_argument("--case",action="append",choices=CASES)
    os.environ["HORIZON_NO_AUDIO"]="1"
    run(p.parse_args())
