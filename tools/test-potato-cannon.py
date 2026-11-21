#!/usr/bin/env python3
"""Compare a real Potato Cannon click with the pinned Java launch fixture."""
import argparse
import csv
from importlib import import_module
import math
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

placement = import_module("test-package-placement")
filters = placement.package.filters
editor = placement.editor
ORIGIN = (8.5, 101.0, 3.5)
CANNON = "create:potato_cannon"
PROJECTILE = "create:potato_projectile"


def number_list(s):
    return tuple(float(x.strip().removesuffix("d")) for x in s.strip("[]").split(","))


def state(host):
    reply = host.command(f"/data get entity @e[type={PROJECTILE},limit=1]")
    if "entity data: " not in reply:
        return None
    raw = reply.split("entity data: ", 1)[1]
    pos = number_list(re.search(r"\bPos:\s*(\[[^\]]*\])", raw)[1])
    vel = number_list(re.search(r"\bMotion:\s*(\[[^\]]*\])", raw)[1])
    return tuple(x - y for x, y in zip(pos, ORIGIN, strict=True)) + vel


def run(args):
    with (ROOT / "fixtures/potato-cannon-launch-java.csv").open() as f:
        java = {r["case"]: r for r in csv.DictReader(f)}
    with (ROOT / "fixtures/potato-cannon-flight-java.csv").open() as f:
        flight = list(csv.DictReader(f))
    with TemporaryDirectory(prefix="hc-potato-") as tmp:
        with fixture_world(args, "PotatoCannon", render=True, pack=args.pack) as host:
            host.commands(("/fill 5 100 0 12 100 16 minecraft:stone", "/fill 5 101 0 12 106 16 minecraft:air"))
            with filters.actor_for(host, args, Path(tmp) if args.lan else None) as (actor, name):
                host.commands((f"/gamemode survival {name}", f"/clear {name}",
                    f"/tp {name} {ORIGIN[0]} {ORIGIN[1]} {ORIGIN[2]} 0 0",
                    f"/item replace entity {name} hotbar.0 with {CANNON}"))
                editor.wait_for(actor, "the actor's launch position", lambda:
                    tuple(actor.call("state")["player"]["position"][:3]) == ORIGIN)
                actor.call("key", "1", "tap")
                editor.wait_for(actor, "the cannon in hand", lambda: (actor.call("inventory")["held"] or {}).get("item") == CANNON)
                actor.call("mouse", "right", "click")
                assert state(host) is None
                assert actor.call("inventory")["held"]["durability_left"] == 100
                actor.call("wait", 10)
                host.command(f"/item replace entity {name} hotbar.1 with minecraft:stick 3")
                editor.wait_for(actor, "unsupported stick ammunition", lambda:
                    actor.call("inventory")["counts"].get("minecraft:stick") == 3)
                actor.call("mouse", "right", "click")
                actor.call("wait", 3)
                inventory = actor.call("inventory")
                assert state(host) is None
                assert inventory["counts"].get("minecraft:stick") == 3
                assert inventory["held"]["durability_left"] == 100
                host.command(f"/item replace entity {name} hotbar.1 with minecraft:potato 3")
                editor.wait_for(actor, "three potatoes", lambda: actor.call("inventory")["counts"].get("minecraft:potato") == 3)
                actor.call("mouse", "right", "click")
                editor.wait_for(host, "the projectile", lambda: state(host) is not None)
                editor.wait_for(actor, "the consumed potato", lambda: actor.call("inventory")["counts"].get("minecraft:potato") == 2)
                expected = tuple(float(java["potato"][k]) for k in ("x", "y", "z", "vx", "vy", "vz"))
                actual = state(host)
                assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(actual, expected, strict=True)), (actual, expected)
                assert actor.call("inventory")["held"]["durability_left"] == 99
                actor.call("mouse", "right", "click")
                assert actor.call("inventory")["counts"].get("minecraft:potato") == 2
                start = host.clock()
                for row in flight:
                    host.step_to(start + int(row["tick"]))
                    expected = tuple(float(row[k]) for k in ("x", "y", "z", "vx", "vy", "vz"))
                    actual = state(host)
                    assert actual is not None and all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(actual, expected, strict=True)), (row["tick"], actual, expected)
    print("Empty and unsupported ammo were rejected; loaded clicks and three flight ticks matched Java.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        p.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    p.add_argument("--lan", action="store_true")
    os.environ["HORIZON_NO_AUDIO"] = "1"
    run(p.parse_args())
