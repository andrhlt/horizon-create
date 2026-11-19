#!/usr/bin/env python3
"""Replay Java's physical Package throw-owner lifetime on overlap."""

import argparse
from collections import defaultdict
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

stack = import_module("test-package-stack")
throw = import_module("test-package-throw")
ORIGIN = (8.5, 105.0, -11.5)
BOX = "@e[type=create:package,tag=OwnedPackage,limit=1]"
SUPPORT = {"above": 0.25, "level": 0.0, "package": 0.0, "clear": 0.55}


def seed(host, owner_name, case):
    x, y, z = ORIGIN
    at = (x + 0.375, y + SUPPORT[case], z)
    coords = stack.placement.editor.xyz(at)
    if case == "package":
        host.command(f'/summon create:package {coords} {{NoGravity:1b,Health:5f,Fire:-1s,'
                     'equipment:{mainhand:{id:"create:cardboard_package_10x8",count:1}}}')
    else:
        host.command(f'/summon minecraft:pig {coords} {{NoAI:1b,NoGravity:1b,PersistenceRequired:1b}}')
    owner = throw.uuid_value(host.command(f"/data get entity {owner_name} UUID"))
    uuid = ','.join(map(str, owner))
    coords = stack.placement.editor.xyz(ORIGIN)
    host.command(f'/summon create:package {coords} {{Tags:["OwnedPackage"],NoGravity:1b,Health:5f,Fire:-1s,'
                 f'CreatePackageTossedBy:[I;{uuid}],'
                 'equipment:{mainhand:{id:"create:cardboard_package_10x8",count:1}}}')
    return owner


def replay(host, actor, owner_name, case, rows):
    owner = seed(host, owner_name, case)
    expected_count = 2 if case == "package" else 1
    if actor is not host:
        stack.placement.editor.wait_for(actor, "the owned Package and its contact in LAN view",
                                        lambda: len(stack.placement.witness(actor)) == expected_count)
    start = host.clock()
    differing = []
    for row in rows:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        assert len(stack.vector(host.command(f"/data get entity {BOX} Pos"))) == 3
        expected = owner if row["owned"] == "true" else None
        reply = host.command(f"/data get entity {BOX} CreatePackageTossedBy")
        observed = throw.uuid_value(reply) if "entity data:" in reply else None
        if observed != expected:
            differing.append(tick)
    print(f"{case}: {len(rows)} rows, mismatched ticks {differing}", flush=True)
    return not differing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for label in ("ctl", "client", "resources"):
        parser.add_argument(label, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/package-contact-owner-java.csv")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    grouped = defaultdict(list)
    with args.reference.open(newline="") as source:
        for row in csv.DictReader(source):
            grouped[row["case"]].append(row)
    assert len(grouped) == 4 and sum(map(len, grouped.values())) == 32
    outcomes = []
    for case, rows in grouped.items():
        scenario = f"PackageContactOwner{case}" + ("Guest" if args.lan else "")
        with TemporaryDirectory(prefix="hc-ownership-") as scratch, fixture_world(args, scenario, pack=args.pack) as host:
            host.commands(("/fill 5 104 -15 12 110 -8 minecraft:air",
                           "/fill 5 103 -15 12 103 -8 minecraft:obsidian"))
            with stack.placement.package.filters.actor_for(host, args, Path(scratch) if args.lan else None) as (actor, name):
                stack.placement.teleport(host, actor, name, (8.5, 104.0, -13.5))
                outcomes.append(replay(host, actor, name, case, rows))
    raise SystemExit(not all(outcomes))


if __name__ == "__main__":
    main()
