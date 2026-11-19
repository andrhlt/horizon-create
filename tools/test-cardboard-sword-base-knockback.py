#!/usr/bin/env python3
"""Observe real pig knockback with a nonzero attack-knockback base."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

sword = import_module("test-cardboard-sword")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/cardboard-sword-base-knockback-java.csv").open(newline="") as reference:
        row = next(csv.DictReader(reference))
    expected = tuple(float(row[key]) for key in ("health", "vx", "vy", "vz"))
    scenario = "SwordBonusMobLAN" if args.lan else "SwordBonusMobSolo"
    with TemporaryDirectory(prefix="hc-bonus-mob-") as scratch:
        with fixture_world(args, scenario, render=True, pack=args.pack) as host:
            host.commands((
                "/fill 0 100 -4 20 100 14 minecraft:smooth_stone",
                "/fill 0 101 -4 20 106 14 minecraft:air",
                "/time set midnight",
            ))
            with sword.package.filters.actor_for(host, args, Path(scratch) if args.lan else None) as (actor, name):
                host.commands((
                    f"/gamemode survival {name}",
                    f"/attribute {name} minecraft:attack_knockback base set 2",
                    f"/item replace entity {name} weapon.mainhand with {sword.SWORD}",
                ))
                x, y, z = sword.ORIGIN
                sword.placement.teleport(host, actor, name, (x, y, z - 2))
                host.command(f"/summon minecraft:pig {x} {y} {z} {{PersistenceRequired:1b,Tags:[sword_target]}}")
                host.command(f"/attribute {sword.TARGET} minecraft:movement_speed base set 0")
                host.step_to(host.clock() + 1)
                host.step_to(host.clock() + 1)
                assert sword.entity_data(host, sword.TARGET, "OnGround") == "1b"
                sword.aim(actor, "pig", 0)
                actor.call("wait", 14)
                actor.call("mouse", "left", "click")
                sword.placement.editor.wait_for(host, "the real nonzero impulse", lambda: sword.sample(host)[6] > 0)
                impact = sword.sample(host)
                print(f"Pig impact with base knockback 2: health {impact[0]}, motion {impact[4:7]}")
                assert (impact[0], *impact[4:7]) == expected, (expected, impact)


if __name__ == "__main__":
    main()
