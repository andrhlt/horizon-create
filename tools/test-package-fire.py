#!/usr/bin/env python3
"""Compare Package ignition and burning to the pinned Java GameTest."""
import argparse
from collections import defaultdict
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

placement = import_module("test-package-placement")
package = placement.package
BASE = (8, 104, -12)
AT = (8.5, 104.0, -11.5)
SELECTOR = "@e[type=create:package,limit=1]"
FIRE_DAMAGE = f"/damage {SELECTOR} 1 minecraft:in_fire"
CONTACTS = {
    "dry": "minecraft:air",
    "campfire": "minecraft:campfire",
    "flame": "minecraft:fire",
    "lava": "minecraft:lava[level=0]",
    "resistant": "minecraft:fire",
    "repeated": "minecraft:air",
}


def summon(host, scenario):
    resist = ',"minecraft:damage_resistant":{types:"#minecraft:is_fire"}' if scenario == "resistant" else ""
    cargo = '"create:package_contents":[{slot:0,item:{id:"minecraft:clay_ball",count:3}}]'
    stack = f'{{id:"create:cardboard_package_12x12",count:1,components:{{{cargo}{resist}}}}}'
    options = f"{{Silent:1b,PersistenceRequired:1b,Health:5f,Fire:-1s,equipment:{{mainhand:{stack}}}}}"
    host.call("command", f"/kill {SELECTOR}")
    placement.editor.wait_for(host, "the previous package to leave", lambda: not placement.witness(host))
    host.call("command", "/kill @e[type=minecraft:item]")
    host.command(f"/setblock {placement.editor.xyz(BASE)} {CONTACTS[scenario]}")
    host.command(f"/summon create:package {placement.editor.xyz(AT)} {options}")
    placement.editor.wait_for(host, "the fresh package to enter the world", lambda: len(placement.witness(host)) == 1)
    return placement.witness(host)[0]["id"]


def witness(peer, entity):
    return next((value for value in placement.witness(peer) if value["id"] == entity), None)


def cargo_near(peer):
    drops = peer.call("entities", 16, "minecraft:item")["entities"]
    return sum(drop["item"]["count"] for drop in drops if drop["item"]["item"] == "minecraft:clay_ball")


def present(peer, entity, removed, health):
    found = witness(peer, entity)
    if removed:
        return found is None
    return found is not None and abs(found["health"] - health) < 2e-6


def run_case(host, actor, scenario, expected):
    entity = summon(host, scenario)
    if scenario == "dry":
        host.call("command", FIRE_DAMAGE)
    start = host.clock()
    for row in expected:
        tick = int(row["tick"])
        if tick and scenario == "repeated":
            host.call("command", FIRE_DAMAGE)
        elif tick:
            host.step_to(start + tick)
        removed = row["removed"] == "true"
        health = float(row["health"])
        spilled = int(row["spilled"])
        for peer in (host,) if actor is host else (host, actor):
            try:
                placement.editor.wait_for(peer, f"package state for {scenario} at tick {tick}", lambda:
                    present(peer, entity, removed, health) and cargo_near(peer) == spilled
                )
            except RuntimeError as error:
                raise AssertionError(scenario, row, witness(peer, entity), cargo_near(peer)) from error
        if not removed:
            result = host.command(f"/data get entity {SELECTOR} Fire").split("entity data: ", 1)[1]
            assert int(result.removesuffix("s")) == int(row["fire_ticks"]), (scenario, row, result)
    print(f"{scenario}: {len(expected)} frames", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--case", action="append", choices=CONTACTS)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    grouped = defaultdict(list)
    with (ROOT / "fixtures/package-fire-java.csv").open(newline="") as data:
        for row in csv.DictReader(data):
            grouped[row["case"]].append(row)
    scenarios = args.case or tuple(grouped)
    assert sum(map(len, grouped.values())) == 278 and set(grouped) == set(CONTACTS)
    world = "PackageFireGuest" if args.lan else "PackageFireHost"
    with TemporaryDirectory(prefix="hc-package-fire-") as scratch:
        with fixture_world(args, world, render=True, pack=args.pack) as host:
            host.commands((
                "/fill 4 100 -16 16 100 -4 minecraft:obsidian",
                "/fill 4 101 -16 16 112 -4 minecraft:air",
                "/setblock 8 103 -12 minecraft:obsidian",
            ))
            with package.filters.actor_for(host, args, Path(scratch) if args.lan else None) as (actor, name):
                placement.teleport(host, actor, name, (8.5, 101.0, -14.5))
                for scenario in scenarios:
                    run_case(host, actor, scenario, grouped[scenario])
    print(f"Matched {sum(len(grouped[s]) for s in scenarios)} Java Package fire frames.", flush=True)


if __name__ == "__main__":
    main()
