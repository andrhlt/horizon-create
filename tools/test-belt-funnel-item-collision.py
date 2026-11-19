#!/usr/bin/env python3
"""Replay the original item-only collision plane of a pulling Belt Funnel."""
from argparse import ArgumentParser
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

ORIGIN = (8, 172, -12)


def selector(item):
    return ('@e[type=minecraft:item,x=7,y=170,z=-13,dx=2,dy=4,dz=2,'
            f'nbt={{Item:{{id:"minecraft:{item}"}}}},limit=1]')


def vertical(data):
    found = re.search(r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)[dD]?\s*$", data)
    assert found, data
    return float(found[1]) - ORIGIN[1]


def main():
    parser = ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/belt-funnel-item-collision-java.csv")
    args = parser.parse_args()
    with args.reference.open() as stream:
        rows = list(csv.reader(stream))[1:]
    with fixture_world(args, "FunnelItemCollision", pack=args.pack) as host:
        host.commands((
            "/fill 7 170 -13 9 176 -11 minecraft:air",
            "/fill 7 170 -13 9 170 -11 minecraft:stone",
            "/setblock 8 172 -12 create:brass_belt_funnel[facing=north,shape=pulling] strict",
        ))
        for name, z in (("iron_ingot", -11.5), ("gold_ingot", -11.09)):
            host.command(f'/summon minecraft:item 8.5 173.65 {z} {{Item:{{id:"minecraft:{name}",count:1}},'
                         'PickupDelay:32767s,Motion:[0.0d,0.0d,0.0d]}')
        start = host.clock()
        mismatches = []
        for raw in rows:
            tick = int(raw[0])
            if tick:
                host.step_to(start + tick)
            observations = host.commands(
                f"/data get entity {selector(item)} {path}"
                for item in ("iron_ingot", "gold_ingot")
                for path in ("Pos[1]", "OnGround")
            )
            actual = (vertical(observations[0]), observations[1].endswith("1b"),
                      vertical(observations[2]), observations[3].endswith("1b"))
            expected = (float(raw[1]), raw[2] == "true", float(raw[3]), raw[4] == "true")
            print(tick, actual, expected, flush=True)
            if any(abs(actual[i] - expected[i]) > .000002 for i in (0, 2)) or actual[1::2] != expected[1::2]:
                mismatches.append((tick, actual, expected))
    assert not mismatches, f"{len(mismatches)} item collision ticks differed. First: {mismatches[:5]}"
    print(f"Matched all {len(rows)} ticks for both Java item collision lanes.")


if __name__ == "__main__":
    main()
