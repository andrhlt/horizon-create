#!/usr/bin/env python3
"""Compare Java's vertical entity overlap and Package impulses."""

import argparse
from collections import defaultdict
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

stack = import_module("test-package-stack")
mp = import_module("test-multiplayer")
ORIGIN = (8.5, 105.0, -11.5)
BOX = "@e[type=create:package,tag=ContactBox,limit=1]"
PIG = "@e[type=minecraft:pig,tag=ContactPig,limit=1]"
SCENARIOS = {"above": 0.25, "level": 0.0, "below": -0.25, "clear": 0.55}
FIELDS = (("ax", "ay", "az"), ("avx", "avy", "avz"), ("bx", "by", "bz"))


def seed(host, case):
    host.call("command", "/kill @e[tag=ContactBox]")
    host.call("command", "/kill @e[tag=ContactPig]")
    x, y, z = ORIGIN
    host.commands((
        f'/summon minecraft:pig {x + 0.375} {y + SCENARIOS[case]} {z} '
        '{NoAI:1b,NoGravity:1b,Tags:["ContactPig"],PersistenceRequired:1b}',
        f'/summon create:package {x} {y} {z} '
        '{NoGravity:1b,Tags:["ContactBox"],Health:5f,Fire:-1s,'
        'equipment:{mainhand:{id:"create:cardboard_package_10x8",count:1}}}',
    ))


def relative(position):
    return tuple(value - origin for value, origin in zip(position, ORIGIN, strict=True))


def observe(host):
    box_pos, box_motion, pig_pos = map(stack.vector, host.commands((
        f"/data get entity {BOX} Pos",
        f"/data get entity {BOX} Motion",
        f"/data get entity {PIG} Pos",
    )))
    return relative(box_pos), box_motion, relative(pig_pos)


def replay(host, actor, case, reference):
    seed(host, case)
    start = host.clock()
    differences = []
    for row in reference:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        observed = observe(host)
        expected = tuple(tuple(float(row[field]) for field in fields) for fields in FIELDS)
        if any(not stack.placement.same(actual, wanted, 2e-6)
               for actual, wanted in zip(observed, expected, strict=True)):
            differences.append((tick, expected, observed))
    if actor is not host and not differences:
        displaced = case != "clear"
        mp.until("the Package displacement to reach the live observer", lambda: any(
            (body["pos"][0] < ORIGIN[0] - 0.01) if displaced
            else stack.placement.same(body["pos"], ORIGIN, 2e-4)
            for body in stack.placement.witness(actor)
        ))
    print(f"{case} {len(reference)} rows {len(differences)} differences {differences[:2]}", flush=True)
    return not differences


def check_joined_pose(host, args, scratch, case, target):
    name = "ContactWitness"
    port = host.call("lan", "status")["port"]
    with mp.joined_client(args, scratch, f"127.0.0.1:{port}", name,
                          scenario=f"package-contact-{case}", pack=args.pack) as witness:
        mp.until("the fresh final-pose observer to join", lambda: any(
            p["name"] == name and p["placed"] for p in host.call("lan", "status")["guests"]
        ))
        stack.placement.teleport(host, witness, name, (8.5, 104.0, -13.5))
        positions = lambda: [body["pos"] for body in stack.placement.witness(witness)]
        try:
            mp.until("the Package spawn position to reach the fresh observer", lambda: any(
                stack.placement.same(position, target, 2e-4) for position in positions()
            ))
        except RuntimeError as error:
            raise RuntimeError(f"{case} guest spawn positions {positions()} differed from {target}") from error
        print(f"{case}: live LAN displacement and fresh guest final spawn verified", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--case", choices=SCENARIOS)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/package-vertical-contact-java.csv")
    args = parser.parse_args()
    grouped = defaultdict(list)
    with args.reference.open(newline="") as source:
        for row in csv.DictReader(source):
            grouped[row["case"]].append(row)
    assert len(grouped) == 4 and sum(map(len, grouped.values())) == 48
    results = []
    cases = (args.case,) if args.case else grouped
    for case in cases:
        rows = grouped[case]
        scenario = "PackageVerticalContact" + case + ("Guest" if args.lan else "")
        with TemporaryDirectory(prefix="hc-contact-") as scratch, fixture_world(args, scenario, pack=args.pack) as host:
            host.commands(("/fill 5 104 -15 12 110 -8 minecraft:air",
                           "/fill 5 103 -15 12 103 -8 minecraft:obsidian"))
            with stack.placement.package.filters.actor_for(host, args, Path(scratch) if args.lan else None) as (actor, name):
                stack.placement.teleport(host, actor, name, (8.5, 104.0, -13.5))
                matched = replay(host, actor, case, rows)
            if args.lan and matched:
                target = tuple(at + float(rows[-1][key]) for at, key in zip(ORIGIN, FIELDS[0], strict=True))
                check_joined_pose(host, args, Path(scratch), case, target)
            results.append(matched)
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
