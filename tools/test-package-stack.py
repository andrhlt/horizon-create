#!/usr/bin/env python3
"""Compare physical Package stacking with the pinned Java Create fixture."""

import argparse
from collections import defaultdict
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

placement = import_module("test-package-placement")
ORIGIN = (8.5, 104.0, -11.5)
UPPER = "@e[type=create:package,tag=StackUpper,limit=1]"
SUPPORT = "@e[tag=StackLower,limit=1]"
OBSERVATIONS = ((UPPER, "Pos"), (UPPER, "Motion"), (SUPPORT, "Pos"), (UPPER, "OnGround"))
FIELDS = (("x", "y", "z"), ("vx", "vy", "vz"), ("sx", "sy", "sz"))
TOLERANCE = 2e-6


def summon(host, case):
    host.call("command", "/kill @e[tag=StackUpper]")
    host.call("command", "/kill @e[tag=StackLower]")
    start = placement.editor.xyz(ORIGIN)
    if case == "pig":
        host.command(f'/summon minecraft:pig {start} {{NoAI:1b,Tags:["StackLower"],PersistenceRequired:1b}}')
    else:
        model = "10x8" if case == "narrowBelow" else "12x12"
        host.command(f'/summon create:package {start} {{Tags:["StackLower"],Health:5f,Fire:-1s,'
                     f'equipment:{{mainhand:{{id:"create:cardboard_package_{model}",count:1}}}}}}')
    offset = {"edge": 0.68, "miss": 0.70}.get(case, 0.0)
    x, y, z = ORIGIN
    above = placement.editor.xyz((x + offset, y + 2.5, z))
    host.command(f'/summon create:package {above} {{Tags:["StackUpper"],Health:5f,Fire:-1s,'
                 'equipment:{mainhand:{id:"create:cardboard_package_10x8",count:1}},Motion:[0d,-0.12d,0d]}')


def vector(reply):
    data = reply.split("entity data: ", 1)[1]
    return tuple(float(value.strip().removesuffix("d")) for value in data.strip("[]").split(","))


def relative(position):
    return tuple(value - origin for value, origin in zip(position, ORIGIN, strict=True))


def run_case(host, actor, case, reference):
    summon(host, case)
    expected_packages = 1 if case == "pig" else 2
    if actor is not host:
        placement.editor.wait_for(actor, f"the {expected_packages} original Packages in {case}",
                                  lambda: len(placement.witness(actor)) == expected_packages)
    start = host.clock()
    for row in reference:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        replies = host.commands(
            f"/data get entity {target} {field}"
            for target, field in OBSERVATIONS
        )
        coords = relative(vector(replies[0])), vector(replies[1]), relative(vector(replies[2]))
        for observed, fields in zip(coords, FIELDS, strict=True):
            expected = tuple(float(row[field]) for field in fields)
            assert placement.same(observed, expected, TOLERANCE), (case, tick, fields, expected, observed)
        grounded = replies[3].rsplit(" ", 1)[-1] == "1b"
        assert grounded == (row["grounded"] == "true"), (case, tick, row["grounded"], grounded, replies[3])
    if actor is not host:
        expected_top = tuple(base + float(reference[-1][axis]) for base, axis in zip(ORIGIN, "xyz", strict=True))
        placement.editor.wait_for(actor, f"the final Package position to reach the LAN guest in {case}",
                                  lambda: any(placement.same(body["pos"], expected_top, 2e-4)
                                              for body in placement.witness(actor)))
    print(f"{case}: {len(reference)} exact authority frames", flush=True)


def check_reopened_stack(host, player_position, reference):
    host.restart()
    placement.teleport(host, host, "@s", player_position)
    expected_upper = tuple(float(reference[-1][field]) for field in FIELDS[0])
    expected_lower = tuple(float(reference[-1][field]) for field in FIELDS[2])
    start = host.clock()
    for tick in range(10):
        if tick:
            host.step_to(start + tick)
        replies = host.commands((
            f"/data get entity {UPPER} Pos",
            f"/data get entity {SUPPORT} Pos",
        ))
        for reply, expected in zip(replies, (expected_upper, expected_lower), strict=True):
            actual = relative(vector(reply))
            assert placement.same(actual, expected, TOLERANCE), (tick, actual, expected)
    print("The saved stack retained the original settled positions for all 10 ticks after cold reopen.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--reopen", action="store_true")
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/package-stack-java.csv")
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    grouped = defaultdict(list)
    with args.reference.open(newline="") as source:
        for row in csv.DictReader(source):
            grouped[row["case"]].append(row)
    assert sum(map(len, grouped.values())) == 125 and len(grouped) == 5
    cases = args.case or (("wideBelow",) if args.reopen else tuple(grouped))
    if args.reopen and tuple(cases) != ("wideBelow",):
        parser.error("--reopen uses the wideBelow fixture")
    scenario = "PackageStackReopen" if args.reopen else ("PackageStackGuest" if args.lan else "PackageStackHost")
    player_position = (8.5, 104.0, -13.5)
    with TemporaryDirectory(prefix="hc-boxes-") as scratch, fixture_world(
            args, scenario, render=True, pack=args.pack) as host:
        host.commands(("/fill 5 104 -15 12 110 -8 minecraft:air",
                       "/fill 5 103 -15 12 103 -8 minecraft:obsidian"))
        with placement.package.filters.actor_for(host, args, Path(scratch) if args.lan else None) as (actor, name):
            placement.teleport(host, actor, name, player_position)
            for case in cases:
                run_case(host, actor, case, grouped[case])
        if args.reopen:
            check_reopened_stack(host, player_position, grouped["wideBelow"])
    print(f"Matched {sum(len(grouped[case]) for case in cases)} Java Package stacking frames.", flush=True)


if __name__ == "__main__":
    main()
