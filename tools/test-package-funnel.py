#!/usr/bin/env python3
"""Replay original physical Package intake through stationary Funnels."""
import argparse
from collections import defaultdict
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

landing = import_module("test-package-depot")
placement = landing.placement
package = placement.package
FUNNEL = (8, 104, -12)
xyz = placement.editor.xyz


def seed(host, scenario):
    host.call("command", f"/kill {landing.fire.SELECTOR}")
    placement.editor.wait_for(host, "the previous Package to leave", lambda: not placement.witness(host))
    host.commands((
        "/fill 6 104 -14 10 111 -10 minecraft:air",
        "/fill 6 103 -14 10 103 -10 minecraft:obsidian",
    ))
    host.call("command", "/kill @e[type=minecraft:item,x=6,y=103,z=-14,dx=4,dy=6,dz=4]")
    floor = scenario == "floor"
    barrel = (8, 103, -12) if floor else (9, 104, -12)
    host.command(f"/setblock {xyz(barrel)} minecraft:barrel")
    if scenario == "full":
        contents = ",".join(f'{{Slot:{slot}b,id:"minecraft:iron_ingot",count:64}}' for slot in range(27))
        host.command(f"/data merge block {xyz(barrel)} {{Items:[{contents}]}}")
    if scenario == "powered":
        host.command("/setblock 8 104 -11 minecraft:redstone_block")
    kind = "andesite" if scenario == "wallAndesite" else "brass"
    face = "up" if floor else "west"
    extracting = str(scenario == "extracting").lower()
    powered = str(scenario == "powered").lower()
    host.command(f"/setblock {xyz(FUNNEL)} create:{kind}_funnel[facing={face},extracting={extracting},powered={powered}]")
    if scenario == "filtered":
        host.command(f'/data merge block {xyz(FUNNEL)} {{Filter:{{id:"minecraft:iron_ingot",count:1}}}}')
    host.step_to(host.clock() + 1)
    cargo = '"create:package_contents":[{slot:6,item:{id:"minecraft:clay_ball",count:3}}]'
    stack = ('{id:"create:cardboard_package_10x8",count:1,components:{'
             f'"create:package_address":"Funnel fixture",{cargo}' + '}}')
    at = (8.28, 106.05, -11.63) if floor else (8.30, 104.15, -11.40)
    opts = (f"{{Silent:1b,PersistenceRequired:1b,Health:5f,Fire:-1s,equipment:{{mainhand:{stack}}},"
            "Motion:[0d,-0.12d,0d],Rotation:[47f,0f]}")
    host.command(f"/summon create:package {xyz(at)} {opts}")
    placement.editor.wait_for(host, "the new Funnel Package to arrive", lambda: len(placement.witness(host)) == 1)
    return placement.witness(host)[0]["id"], barrel


def run_case(host, actor, scenario, rows):
    entity, barrel = seed(host, scenario)
    peers = (host,) if actor is host else (host, actor)
    start = host.clock()
    for row in rows:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        removed = row["removed"] == "true"
        for peer in peers:
            placement.editor.wait_for(peer, f"the Package presence in {scenario} at tick {tick}",
                                      lambda: (landing.body(peer, entity) is None) == removed)
        if not removed:
            pos = tuple(value - origin for value, origin in zip(landing.entity_vector(host, "Pos"), FUNNEL, strict=True))
            motion = landing.entity_vector(host, "Motion")
            yaw = landing.entity_vector(host, "Rotation", "f")[0]
            for actual, fields in ((pos, ("x", "y", "z")), (motion, ("vx", "vy", "vz")), ((yaw,), ("yaw",))):
                want = tuple(float(row[key]) for key in fields)
                assert placement.same(actual, want, 2e-6), (scenario, row, fields, actual)
        replies = host.call("command", f"/data get block {xyz(barrel)} Items")["chat"]
        contents = next((line.split("block data: ", 1)[1] for line in replies if "block data: " in line), "[]")
        items = package.parse(contents)
        first = next((item for item in items if item.get("Slot", item.get("slot")) == 0), {})
        stack = {key: value for key, value in first.items() if key not in ("Slot", "slot")}
        stored = stack or {"id": "minecraft:air", "count": 0}
        assert (stored["id"], stored["count"]) == (row["item"], int(row["count"])), (scenario, row, stored)
        iron = sum(item["count"] for item in items if item["id"] == "minecraft:iron_ingot")
        assert iron == int(row["iron_count"]), (scenario, row, iron)
        if row["stack_hex"]:
            java_stack = package.parse(bytes.fromhex(row["stack_hex"]).decode())
            assert stored == java_stack, (scenario, row, stored, java_stack)
    print(f"{scenario}: {len(rows)} frames", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--case", action="append")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    grouped = defaultdict(list)
    with (ROOT / "fixtures/package-funnel-java.csv").open(newline="") as data:
        for row in csv.DictReader(data):
            grouped[row["case"]].append(row)
    assert len(grouped) == 7 and sum(map(len, grouped.values())) == 182
    scenarios = args.case or tuple(grouped)
    world = "PackageFunnelGuest" if args.lan else "PackageFunnelHost"
    with TemporaryDirectory(prefix="hc-package-funnel-") as scratch:
        with fixture_world(args, world, render=True, pack=args.pack) as host:
            host.commands((
                "/fill 4 100 -16 16 100 -4 minecraft:obsidian",
                "/fill 4 101 -16 16 112 -4 minecraft:air",
                "/fill 6 103 -14 10 103 -10 minecraft:obsidian",
            ))
            with package.filters.actor_for(host, args, Path(scratch) if args.lan else None) as (actor, name):
                placement.teleport(host, actor, name, (8.5, 104.0, -13.5))
                for scenario in scenarios:
                    run_case(host, actor, scenario, grouped[scenario])
    print(f"Matched {sum(len(grouped[s]) for s in scenarios)} Java Package Funnel frames.", flush=True)


if __name__ == "__main__":
    main()
