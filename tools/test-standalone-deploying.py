#!/usr/bin/env python3
"""Replay original Belt Deployer cogwheel and copper item applications."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

packager = import_module("test-packager-redstone")


def reference(name):
    with (ROOT / f"fixtures/standalone-deploying-{name}-java.csv").open(newline="") as file:
        return list(csv.DictReader(file))


def at(x, y, z):
    return f"{x} {y} {z}"


def setup(host, starts):
    commands = []
    for (x, y, z), row in zip(starts, reference("setup"), strict=True):
        for index, part in enumerate(("start", "middle", "middle", "end")):
            commands.append(f"/setblock {at(x + index, y, z)} create:belt[facing=east,part={part},slope=horizontal]")
        axes = row["held"]
        if int(row["held_damage"]):
            axes += f"[minecraft:damage={row['held_damage']}]"
        commands.extend((
            f"/setblock {at(x, y, z - 1)} create:creative_motor[facing=south]{{ScrollValue:-64}}",
            f"/setblock {at(x + 1, y + 2, z)} create:deployer[facing=down,axis_along_first=true]",
            f"/setblock {at(x, y + 2, z)} create:creative_motor[facing=east]{{ScrollValue:64}}",
            f"/item replace block {at(x + 1, y + 2, z)} container.0 with {axes} {row['held_count']}",
        ))
    replies = host.commands(commands)
    assert all("Replaced 1 slot" in line for line in replies[7::8]), replies
    start = host.clock()
    for tick in range(1, 5):
        host.step_to(start + tick)


def insert_inputs(host, starts):
    commands = []
    for lane, row in zip(starts, reference("setup"), strict=True):
        commands.append(f'/data merge block {at(*lane)} {{Inventory:{{Items:[{{Item:{{id:"{row["input"]}",count:1}},'
                        'Pos:1.375f,PrevPos:1.375f,InsertedAt:1,InsertedFrom:1}],PositiveOrder:1b}}')
    replies = host.commands(commands)
    assert all("Modified block data" in line for line in replies), replies


def sample(host, tick, starts, rows):
    replies = host.commands(query for x, y, z in starts for query in (
        f"/data get block {at(x, y, z)}", f"/data get block {at(x + 1, y + 2, z)}",
        f"/data get block {at(x, y, z)} Inventory.Items",
    ))
    fields = iter(replies)
    actual = []
    for row in rows:
        belt, machine, stacks = next(fields), next(fields), next(fields)
        belt_rpm = packager.number(belt, "Speed")
        deployer_rpm = packager.number(machine, "Speed")
        phase = packager.string(machine, "State") or "WAITING"
        timer = packager.number(machine, "Timer") or 0
        tool = re.search(r"\bItems:\s*(\[.*\])", machine)
        assert tool, machine
        held = packager.number(tool[1], "count") or 0
        damage = re.search(r'"minecraft:damage":\s*(\d+)', tool[1])
        stacks = list(packager.top_level_entries(stacks.partition("block data: ")[2]))
        transport = packager.string(stacks[0], "id") if stacks else "_"
        locked = str("Locked: 1b" in stacks[0]).lower() if stacks else "_"
        actual.append(dict(zip(row, (str(tick), row["scenario"], str(belt_rpm), str(deployer_rpm),
                                      phase, str(timer), str(held), damage[1] if damage else "0",
                                      transport, locked), strict=True)))
    return actual


def run(args):
    expected = reference("timing")
    last_tick = int(expected[-1]["tick"])
    starts = [(9, 172, 16 + 4 * index) for index in range(len(reference("setup")))]
    actual = []
    with fixture_world(args, "StandaloneDeploying", pack=args.pack, env={"HORIZON_NO_AUDIO": "1"}) as host:
        host.command("/tp @s 13.5 172 22.5")
        setup(host, starts)
        start = host.clock()
        for tick in range(last_tick + 1):
            if tick:
                host.step_to(start + tick)
            rows = [row for row in expected if int(row["tick"]) == tick]
            actual.extend(sample(host, tick, starts, rows))
            if tick == 0:
                insert_inputs(host, starts)
    path = ROOT / ".local" / "standalone-deploying-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=expected[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(actual)
    differences = [(wanted, got) for wanted, got in zip(expected, actual, strict=True) if wanted != got]
    assert not differences, f"{len(differences)} snapshots differed; first three {differences[:3]}. See {path}"
    print(f"Six Belt Deployer scopes matched the Java trace across {last_tick + 1} ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
