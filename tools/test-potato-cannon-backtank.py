#!/usr/bin/env python3
"""Compare potato shots with equipped Copper Backtanks against pinned Java."""
import argparse
import csv
from importlib import import_module
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

placement = import_module("test-package-placement")
filters, editor = placement.package.filters, placement.editor


def tank_air(host, name):
    data = host.command(f"/data get entity {name} equipment.chest")
    m = re.search(r'"create:banktank_air":\s*(-?\d+)', data)
    return int(m[1]) if m else None


def run(args):
    with (ROOT / "fixtures/potato-cannon-backtank-java.csv").open() as f:
        rows = list(csv.DictReader(f))
    if args.baseline:
        rows = [next(row for row in rows if row["initial_air"] == "100")]
    with TemporaryDirectory(prefix="hc-potato-tank-") as tmp:
        with fixture_world(args, "PotatoTank", render=True, pack=args.pack) as host:
            host.commands(("/fill 6 170 20 11 170 27 minecraft:stone", "/fill 6 171 20 11 175 30 minecraft:air"))
            with filters.actor_for(host, args, Path(tmp) if args.lan else None) as (actor, name):
                host.command(f"/gamemode survival {name}")
                for i, row in enumerate(rows):
                    air = int(row["initial_air"])
                    if i:
                        for _ in range(16): host.step_to(host.clock() + 1)
                    host.commands((f"/clear {name}",
                        f"/tp {name} 8.5 171 25.5 0 0", "/setblock 9 171 24 create:copper_backtank",
                        f"/data merge block 9 171 24 {{Air:{air}}}"))
                    editor.wait_for(actor, "tank reach", lambda: tuple(actor.call("state")["player"]["position"][:3]) == (8.5,171,25.5))
                    actor.call("interact", 9, 171, 24, "up")
                    editor.wait_for(host, "equipped tank", lambda: tank_air(host, name) == air)
                    host.commands((f"/item replace entity {name} hotbar.0 with create:potato_cannon",
                                   f"/item replace entity {name} hotbar.1 with minecraft:potato 3"))
                    actor.call("key", "1", "tap")
                    editor.wait_for(actor, "cannon and ammunition", lambda:
                        (actor.call("inventory")["held"] or {}).get("item") == "create:potato_cannon"
                        and actor.call("inventory")["counts"].get("minecraft:potato") == 3)
                    actor.call("wait", 10)
                    actor.call("mouse", "right", "click")
                    if args.baseline:
                        actor.call("wait", 10)
                        inv = actor.call("inventory")
                        assert inv["counts"].get("minecraft:potato") == 3 and tank_air(host,name) == air, inv
                        print("Baseline reproduced: charged tank prevents the shot.")
                        return
                    editor.wait_for(actor, "shot consumes a potato", lambda: actor.call("inventory")["counts"].get("minecraft:potato") == int(row["ammo"]))
                    editor.wait_for(host, "tank air reconciles", lambda: tank_air(host, name) == int(row["air"]))
                    held = actor.call("inventory")["held"]
                    assert held.get("damage", 0) == int(row["damage"]), (air, held, row)
                    reply = host.command("/data get entity @e[type=create:potato_projectile,limit=1]")
                    assert "entity data: " in reply, (air, reply)
                    host.command("/kill @e[type=create:potato_projectile]")
                    print(f"air {air}: {row['air']} remaining, cannon damage {row['damage']}", flush=True)
    print("Copper Backtank potato shots matched pinned Java.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        p.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    p.add_argument("--lan", action="store_true")
    p.add_argument("--baseline", action="store_true")
    os.environ["HORIZON_NO_AUDIO"] = "1"
    run(p.parse_args())
