#!/usr/bin/env python3
"""Compare original physical Packages centering and entering Chutes."""
import argparse
from collections import defaultdict
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

placement = import_module("test-package-placement")
package = placement.package
fire = import_module("test-package-fire")
CHUTE = (8, 104, -12)
POWER = (9, 104, -12)
BASE = (8.5, 105.0, -11.5)
AT = (8.72, 106.75, -11.33)


def entity_vector(host, key, suffix="d"):
    reply = host.command(f"/data get entity {fire.SELECTOR} {key}").split("entity data: ", 1)[1]
    return tuple(float(value.strip().removesuffix(suffix)) for value in reply.strip("[]").split(","))


def contents(host):
    def read(path, default):
        replies = host.call("command", f"/data get block {placement.editor.xyz(CHUTE)} {path}")["chat"]
        for reply in replies:
            if "block data: " in reply:
                return package.parse(reply.split("block data: ", 1)[1])
        return default

    item = read("Item", {})
    if not item:
        items = read("Items", [])
        if items:
            item = {k: v for k, v in items[0].items() if k not in ("Slot", "slot")}
    return item or {"id": "minecraft:air", "count": 0}


def seed(host, scenario):
    host.call("command", f"/kill {fire.SELECTOR}")
    placement.editor.wait_for(host, "the previous package to leave", lambda: not placement.witness(host))
    host.call("command", f"/setblock {placement.editor.xyz(CHUTE)} minecraft:air")
    host.call("command", f"/setblock {placement.editor.xyz(POWER)} minecraft:air")
    block = f"create:smart_chute[powered={'true' if scenario == 'smart_powered' else 'false'}]" \
        if scenario.startswith("smart") else "create:chute[facing=down,shape=normal]"
    host.command(f"/setblock {placement.editor.xyz(CHUTE)} {block}")
    if scenario == "smart_powered":
        host.command(f"/setblock {placement.editor.xyz(POWER)} minecraft:redstone_block")
    if scenario == "blocked":
        host.command(f'/data merge block {placement.editor.xyz(CHUTE)} '
                     '{Item:{id:"minecraft:iron_ingot",count:64},ItemPosition:1f}')
    cargo = '"create:package_contents":[{slot:6,item:{id:"minecraft:clay_ball",count:3}}]'
    stack = ('{id:"create:cardboard_package_10x8",count:1,components:{'
             f'"create:package_address":"Chute fixture",{cargo}' + '}}')
    options = (f"{{Silent:1b,PersistenceRequired:1b,Health:5f,Fire:-1s,equipment:{{mainhand:{stack}}},"
               "Motion:[0d,-0.12d,0d],Rotation:[47f,0f]}")
    host.command(f"/summon create:package {placement.editor.xyz(AT)} {options}")
    placement.editor.wait_for(host, "the new chute package to arrive", lambda: len(placement.witness(host)) == 1)
    return placement.witness(host)[0]["id"]


def body(peer, entity):
    return next((value for value in placement.witness(peer) if value["id"] == entity), None)


def run_case(host, actor, scenario, expected):
    entity = seed(host, scenario)
    start = host.clock()
    for row in expected:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        removed = row["removed"] == "true"
        for peer in (host,) if actor is host else (host, actor):
            placement.editor.wait_for(peer, f"the Package presence for {scenario} at tick {tick}",
                                      lambda: (body(peer, entity) is None) == removed)
        if not removed:
            pos = tuple(value - base for value, base in zip(entity_vector(host, "Pos"), BASE, strict=True))
            motion = entity_vector(host, "Motion")
            yaw = entity_vector(host, "Rotation", "f")[0]
            for actual, fields in ((pos, ("x", "y", "z")), (motion, ("vx", "vy", "vz")), ((yaw,), ("yaw",))):
                want = tuple(float(row[key]) for key in fields)
                assert placement.same(actual, want, 2e-6), (scenario, row, fields, actual)
        stored = contents(host)
        assert (stored["id"], stored["count"]) == (row["item"], int(row["count"])), (scenario, row, stored)
        if row["stack_hex"]:
            java_stack = package.parse(bytes.fromhex(row["stack_hex"]).decode())
            assert stored == java_stack, (scenario, row, stored, java_stack)
    print(f"{scenario}: {len(expected)} frames", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--case", action="append")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    grouped = defaultdict(list)
    with (ROOT / "fixtures/package-chute-java.csv").open(newline="") as data:
        for row in csv.DictReader(data):
            grouped[row["case"]].append(row)
    scenarios = args.case or tuple(grouped)
    assert len(grouped) == 4 and sum(map(len, grouped.values())) == 92
    world = "PackageChuteGuest" if args.lan else "PackageChuteHost"
    with TemporaryDirectory(prefix="hc-package-chute-") as scratch:
        with fixture_world(args, world, render=True, pack=args.pack) as host:
            host.commands((
                "/fill 4 100 -16 16 100 -4 minecraft:obsidian",
                "/fill 4 101 -16 16 112 -4 minecraft:air",
                "/fill 6 103 -14 10 103 -10 minecraft:obsidian",
            ))
            with package.filters.actor_for(host, args, Path(scratch) if args.lan else None) as (actor, name):
                placement.teleport(host, actor, name, (8.5, 101.0, -14.5))
                for scenario in scenarios:
                    run_case(host, actor, scenario, grouped[scenario])
    print(f"Matched {sum(len(grouped[s]) for s in scenarios)} Java Package Chute frames.", flush=True)


if __name__ == "__main__":
    main()
