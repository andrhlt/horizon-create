#!/usr/bin/env python3
"""Compare original physical Packages landing on Depots and Weighted Ejectors."""
import argparse
from collections import defaultdict
import csv
import os
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

placement = import_module("test-package-placement")
package = placement.package
fire = import_module("test-package-fire")
DEPOT = (8, 104, -12)
BASE = (8.5, 104.8125, -11.5)
AT = (8.72, 106.5625, -11.33)
EJECTOR_TARGET = (12, 104, -12)


def entity_vector(host, key, suffix="d"):
    reply = host.command(f"/data get entity {fire.SELECTOR} {key}").split("entity data: ", 1)[1]
    return tuple(float(value.strip().removesuffix(suffix)) for value in reply.strip("[]").split(","))


def read_block(host, path, default):
    replies = host.call("command", f"/data get block {placement.editor.xyz(DEPOT)} {path}")["chat"]
    for reply in replies:
        if "block data: " in reply:
            data = reply.split("block data: ", 1)[1]
            if path == "BeltPosition":
                return float(data.removesuffix("f"))
            return package.parse(data)
    return default


def contents(host):
    item = read_block(host, "HeldItem.Item", {})
    if not item:
        items = read_block(host, "Items", [])
        if items:
            item = {k: v for k, v in items[0].items() if k not in ("Slot", "slot")}
    return item or {"id": "minecraft:air", "count": 0}


def playback(peer):
    prefix = "CREATE_ELEVATOR_PLAYBACK create:depot_plop,"
    log = peer.socket.parent / "ctl.log"
    return [
        line.split(prefix, 1)[1].split(",")
        for line in log.read_text().splitlines() if prefix in line
    ]


def seed(host, scenario, ejector):
    host.call("command", f"/kill {fire.SELECTOR}")
    placement.editor.wait_for(host, "the previous package to leave", lambda: not placement.witness(host))
    host.call("command", f"/setblock {placement.editor.xyz(DEPOT)} minecraft:air")
    if ejector:
        state = "RETRACTING" if scenario == "retracting" else "CHARGED"
        lid = "1.0f" if scenario == "retracting" else "0.0f"
        host.command(f'/setblock {placement.editor.xyz(DEPOT)} create:weighted_ejector[facing=east]'
                     f'{{State:"{state}",Lid:{{Value:{lid}}},HorizontalDistance:4,VerticalDistance:0}}')
        target = placement.editor.xyz(EJECTOR_TARGET)
        host.call("command", f"/setblock {target} minecraft:air")
        host.command(f"/setblock {target} create:depot")
        host.command(f'/data merge block {target} '
                     '{Items:[{Slot:0b,id:"minecraft:iron_ingot",count:64}],BeltPosition:0.5f}')
    else:
        host.command(f"/setblock {placement.editor.xyz(DEPOT)} create:depot")
    if scenario == "occupied":
        storage = ('{Items:[{Slot:0b,id:"minecraft:iron_ingot",count:64}],BeltPosition:0.5f}' if ejector else
                   '{HeldItem:{Item:{id:"minecraft:iron_ingot",count:64},Pos:0.5f},BeltPosition:0.5f}')
        host.command(f'/data merge block {placement.editor.xyz(DEPOT)} {storage}')
    cargo = '"create:package_contents":[{slot:6,item:{id:"minecraft:clay_ball",count:3}}]'
    address = "Ejector fixture" if ejector else "Depot fixture"
    stack = ('{id:"create:cardboard_package_10x8",count:1,components:{'
             f'"create:package_address":"{address}",{cargo}' + '}}')
    options = (f"{{Silent:1b,PersistenceRequired:1b,Health:5f,Fire:-1s,equipment:{{mainhand:{stack}}},"
               "Motion:[0d,-0.12d,0d],Rotation:[47f,0f]}")
    host.command(f"/summon create:package {placement.editor.xyz(AT)} {options}")
    placement.editor.wait_for(host, "the depot package to arrive", lambda: len(placement.witness(host)) == 1)
    return placement.witness(host)[0]["id"]


def body(peer, entity):
    return next((value for value in placement.witness(peer) if value["id"] == entity), None)


def run_case(host, actor, scenario, expected, ejector):
    entity = seed(host, scenario, ejector)
    peers = (host,) if actor is host else (host, actor)
    heard_before = {peer: len(playback(peer)) for peer in peers}
    start = host.clock()
    for row in expected:
        tick = int(row["tick"])
        if ejector and scenario == "launch" and tick == 12:
            host.command(f"/data merge block {placement.editor.xyz(DEPOT)} {{LaunchQueued:1b}}")
        if tick:
            host.step_to(start + tick)
        if ejector:
            assert read_block(host, "State", None) == row["state"], (scenario, row, read_block(host, "State", None))
        removed = row["removed"] == "true"
        for peer in peers:
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
        if removed:
            position = read_block(host, "BeltPosition", None)
            assert position == float(row["storage_pos"]), (scenario, row, position)
        expected_sound = [
            [str(category), "8.5", "104.5", "-11.5", str(volume), str(pitch)]
            for cue in row["plops"].split(";") if cue
            for category, volume, pitch in [cue.split("|")]
        ]
        for peer in peers:
            placement.editor.wait_for(peer, f"the original Depot audio at tick {tick}", lambda:
                playback(peer)[heard_before[peer]:] == expected_sound
            )
    print(f"{scenario}: {len(expected)} frames", flush=True)


def main():
    os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--case", action="append")
    parser.add_argument("--ejector", action="store_true")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    grouped = defaultdict(list)
    reference = "package-ejector-java.csv" if args.ejector else "package-depot-java.csv"
    with (ROOT / "fixtures" / reference).open(newline="") as data:
        for row in csv.DictReader(data):
            grouped[row["case"]].append(row)
    scenarios = args.case or tuple(grouped)
    assert (len(grouped), sum(map(len, grouped.values()))) == ((4, 96) if args.ejector else (2, 46))
    surface = "Ejector" if args.ejector else "Depot"
    world = f"Package{surface}{'Guest' if args.lan else 'Host'}"
    with TemporaryDirectory(prefix="hc-package-depot-") as scratch:
        with fixture_world(args, world, render=True, pack=args.pack) as host:
            host.commands((
                "/fill 4 100 -16 16 100 -4 minecraft:obsidian",
                "/fill 4 101 -16 16 112 -4 minecraft:air",
                "/fill 6 103 -14 10 103 -10 minecraft:obsidian",
            ))
            with package.filters.actor_for(host, args, Path(scratch) if args.lan else None) as (actor, name):
                placement.teleport(host, actor, name, (8.5, 101.0, -14.5))
                for scenario in scenarios:
                    run_case(host, actor, scenario, grouped[scenario], args.ejector)
    print(f"Matched {sum(len(grouped[s]) for s in scenarios)} Java Package {surface} frames.", flush=True)


if __name__ == "__main__":
    main()
