#!/usr/bin/env python3
"""Place a real Weighted Ejector into the Java dry and wet fixture."""
import argparse
import csv
import json
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world


def main(args):
    with (ROOT / "fixtures/weighted-ejector-placement-java.csv").open() as trace:
        rows = csv.reader(trace)
        next(rows)
        expected = list(rows)
    assert len(expected) == 12
    actual = []
    with fixture_world(args, "WeightedEjectorPlacement", pack=args.pack) as control:
        control.commands((
            "/tp @s 14.5 172 25.5",
            "/fill 12 169 22 25 169 35 minecraft:stone",
            "/give @s create:weighted_ejector 12",
        ))
        control.call("wait", 5)
        control.call("select", "create:weighted_ejector")
        for yaw in (0, 90, 180, 270):
            dx, dz = [(0, 1), (-1, 0), (0, -1), (1, 0)][yaw // 90]
            x = 13 + yaw // 30
            for scenario in range(3):
                z = 24 + scenario * 3
                px, pz = x + 2.5, z + 0.5
                control.call("tp", px, 171, pz)
                control.call("look-at", px + dx * 2, 172.62, pz + dz * 2)
                if scenario:
                    control.command(f"/setblock {x} 170 {z} minecraft:water[level={0 if scenario == 1 else 2}]")
                control.call("interact", x, 169, z, "up")
                state = control.call("block", x, 170, z)
                props = dict(re.findall(r"(\w+)=(\w+)", state["state"]))
                actual.append([str(yaw), str(scenario), state["block"],
                               props.get("facing"), props.get("waterlogged")])
    diffs = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    if diffs:
        for want, got in diffs:
            print(want, got)
        raise RuntimeError(f"{len(diffs)} differing weighted ejector placements")
    print("All 12 Java Weighted Ejector placements matched facing and waterlogged state.")


def dispenser(args):
    with (ROOT / "fixtures/weighted-ejector-buckets-java.csv").open() as trace:
        rows = csv.reader(trace)
        next(rows)
        expected = list(rows)
    assert len(expected) == 13
    actual = []
    with fixture_world(args, "WeightedEjectorBuckets", pack=args.pack) as control:
        control.commands((
            "/tp @s 12.5 172 27.5",
            "/setblock 13 169 27 minecraft:stone",
        ))
        control.call("wait", 5)
        control.commands((
            "/setblock 13 170 27 create:weighted_ejector",
            "/setblock 12 170 27 minecraft:dispenser[facing=east]",
            '/data merge block 12 170 27 {Items:[{Slot:0b,id:"minecraft:water_bucket",count:1}]}',
        ))
        start = control.clock()
        for tick in range(13):
            if tick:
                control.step_to(start + tick)
            block, east, bucket = control.call(
                "script",
                script="block 13 170 27\nblock 14 170 27\ncommand "
                       + json.dumps("/data get block 12 170 27 Items"),
            )
            wet = re.search(r"\bwaterlogged=(true|false)", block["state"])
            item = re.search(r'\bid: "([^"]+)"', bucket["chat"][-1])
            level = re.search(r"\blevel=(\d+)", east["state"])
            actual.append([str(tick), block["block"], wet[1] if wet else "absent",
                           item[1] if item else "minecraft:air", east["block"],
                           level[1] if level else "absent"])
            if tick == 0:
                control.command("/setblock 12 171 27 minecraft:redstone_block")
            elif tick == 6:
                control.commands((
                    "/setblock 12 171 27 minecraft:air",
                    '/data merge block 12 170 27 {Items:[{Slot:0b,id:"minecraft:bucket",count:1}]}',
                    "/setblock 12 171 27 minecraft:redstone_block",
                ))
    if actual != expected:
        differences = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
        raise RuntimeError(f"Weighted Ejector dispenser differs: {differences}")
    print("All 13 Java Weighted Ejector dispenser and neighbor-fluid samples matched tick for tick.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    main(args)
    dispenser(args)
