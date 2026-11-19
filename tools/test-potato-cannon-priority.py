#!/usr/bin/env python3
"""Compare supported potato-cannon ammo priority to pinned Java."""
import argparse
import csv
from importlib import import_module
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world
carrot = import_module("test-potato-cannon-carrot")
multiplayer = import_module("test-multiplayer")

CASES = {
    "off_carrot": ("minecraft:carrot", "minecraft:potato", None),
    "off_potato": ("minecraft:potato", "minecraft:carrot", None),
    "first_carrot": (None, "minecraft:carrot", "minecraft:potato"),
    "first_potato": (None, "minecraft:potato", "minecraft:carrot"),
    "first_apple": (None, "minecraft:apple", "minecraft:carrot"),
    "off_beetroot": ("minecraft:beetroot", "minecraft:melon_slice", None),
    "first_golden_carrot": (None, "minecraft:golden_carrot", "minecraft:beetroot"),
    "first_melon": (None, "minecraft:melon_slice", "minecraft:potato"),
}


def run(args):
    with (ROOT / "fixtures/potato-cannon-priority-java.csv").open() as f:
        expected = {row["case"]: row for row in csv.DictReader(f)}
    with TemporaryDirectory(prefix="hc-ammo-priority-") as tmp:
        with fixture_world(args, "PotatoPriority", render=False, pack=args.pack) as host:
            with carrot.actor_for(host, args, Path(tmp)) as (actor, name):
                host.command(f"/gamemode survival {name}")
                for index, (case, (off, first, second)) in enumerate(CASES.items()):
                    if index:
                        actor.call("wait", 20)
                        host.call("command", "/kill @e[type=create:potato_projectile]")
                    host.call("command", f"/clear {name}")
                    host.command(f"/item replace entity {name} hotbar.0 with create:potato_cannon")
                    host.command(f"/item replace entity {name} hotbar.1 with {first} 3")
                    if second: host.command(f"/item replace entity {name} hotbar.2 with {second} 3")
                    if off: host.command(f"/item replace entity {name} weapon.offhand with {off} 3")
                    actor.call("select", "create:potato_cannon")
                    multiplayer.until("ammo in place", lambda: actor.call("inventory")["counts"].get(first) == 3
                                      and (not off or actor.call("inventory")["counts"].get(off) == 3)
                                      and (not second or actor.call("inventory")["counts"].get(second) == 3))
                    actor.call("use-item")
                    row = expected[case]
                    multiplayer.until("selected ammo consumed", lambda: actor.call("inventory")["counts"].get(row["selected"]) == 2)
                    inventory = actor.call("inventory")
                    actual = (inventory["offhand"].get("count", 0), inventory["hotbar"][1].get("count", 0),
                              inventory["hotbar"][2].get("count", 0), inventory["held"].get("damage", 0))
                    want = tuple(int(row[k]) for k in ("offhand", "slot1", "slot2", "damage"))
                    assert actual == want, (case, actual, want)
                    shot = carrot.data(host, "@e[type=create:potato_projectile,limit=1]")
                    assert shot and row["selected"] in shot, (case, shot)
                    print(case, row["selected"], actual, flush=True)
    print("Supported ammunition priority matched Java.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        p.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    p.add_argument("--lan", action="store_true")
    os.environ["HORIZON_NO_AUDIO"] = "1"
    run(p.parse_args())
