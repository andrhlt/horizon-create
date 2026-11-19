#!/usr/bin/env python3
"""Compare the first potato impact on a stationary pig with pinned Java."""
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
filters, editor = placement.package.filters, placement.editor
ORIGIN = (8.5, 101.0, 3.5)
TARGET = "@e[tag=potato_target,limit=1]"


def values(host):
    reply = host.command(f"/data get entity {TARGET}")
    raw = reply.split("entity data: ", 1)[1]
    health = float(re.search(r"\bHealth:\s*([0-9.]+)f", raw)[1])
    def vector(key):
        return tuple(float(x.strip().removesuffix("d")) for x in
                     re.search(rf"\b{key}:\s*\[([^\]]+)\]", raw)[1].split(","))
    pos = tuple(x-y for x,y in zip(vector("Pos"), ORIGIN, strict=True))
    return (health, *pos, *vector("Motion"))


def run(args):
    with (ROOT / "fixtures/potato-cannon-impact-java.csv").open() as f:
        java = {int(row["tick"]): row for row in csv.DictReader(f)}
    with TemporaryDirectory(prefix="hc-potato-impact-") as tmp:
        with fixture_world(args, "PotatoImpact", render=True, pack=args.pack) as host:
            host.commands(("/fill 5 100 0 12 100 16 minecraft:stone",
                           "/fill 5 101 0 12 106 16 minecraft:air"))
            with filters.actor_for(host, args, Path(tmp) if args.lan else None) as (actor, name):
                host.commands((f"/gamemode survival {name}", f"/clear {name}",
                    f"/tp {name} 8.5 101 3.5 0 0",
                    f"/item replace entity {name} hotbar.0 with create:potato_cannon",
                    f"/item replace entity {name} hotbar.1 with minecraft:potato 3",
                    '/summon minecraft:pig 8.0 102.0 8.5 {NoAI:1b,NoGravity:1b,Tags:["potato_target"]}'))
                actor.call("key", "1", "tap")
                editor.wait_for(actor, "cannon", lambda: (actor.call("inventory")["held"] or {}).get("item") == "create:potato_cannon")
                editor.wait_for(actor, "potatoes", lambda: actor.call("inventory")["counts"].get("minecraft:potato") == 3)
                editor.wait_for(actor, "launch position", lambda: tuple(actor.call("state")["player"]["position"][:3]) == ORIGIN)
                actor.call("wait", 10)
                actor.call("mouse", "right", "click")
                editor.wait_for(actor, "shot", lambda: actor.call("inventory")["counts"].get("minecraft:potato") == 2)
                start = host.clock()
                for tick in range(3):
                    if tick: host.step_to(start + tick)
                    actual = values(host)
                    expected = tuple(float(java[tick][k]) for k in ("health", "x", "y", "z", "vx", "vy", "vz"))
                    assert all(math.isclose(a, b, abs_tol=1e-6) for a,b in zip(actual, expected, strict=True)), (tick, actual, expected)
                reply = host.command("/data get entity @e[type=create:potato_projectile,limit=1]")
                assert "entity data: " not in reply, reply
    print("First potato impact damage and knockback matched pinned Java.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        p.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    p.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    p.add_argument("--lan", action="store_true")
    os.environ["HORIZON_NO_AUDIO"] = "1"
    run(p.parse_args())
