#!/usr/bin/env python3
"""Replay the pinned Java Deployer's in-world casing and cardboard applications."""

import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")


def reference(suffix):
    with (ROOT / f"fixtures/deployer-applications-{suffix}-java.csv").open(newline="") as file:
        return list(csv.DictReader(file))


def coords(at):
    return " ".join(map(str, at))


def setup(host, lanes):
    commands = []
    for lane, row in zip(lanes, reference("setup"), strict=True):
        x, y, z = lane
        commands.extend((
            f"/setblock {x} {y + 1} {z} minecraft:redstone_block",
            f"/setblock {x} {y} {z} create:deployer[facing=east,axis_along_first=true]",
            f"/setblock {x} {y - 1} {z} create:creative_motor[facing=up]{{ScrollValue:64}}",
            f"/setblock {x + 2} {y} {z} {row['input']}",
            f"/item replace block {x} {y} {z} container.0 with {row['held']} 2",
        ))
    replies = host.commands(commands)
    assert all("Replaced 1 slot" in reply for reply in replies[4::5]), replies
    start = host.clock()
    for tick in range(1, 4):
        host.step_to(start + tick)
    host.commands(f"/setblock {x} {y + 1} {z} minecraft:air" for x, y, z in lanes)


def inspect(host, lanes, rows):
    entities = host.commands(f"/data get block {coords(at)}" for at in lanes)
    targets = host.call("script", script="".join(f"block {x + 2} {y} {z}\n" for x, y, z in lanes))
    actual = []
    for expected, nbt, target in zip(rows, entities, targets, strict=True):
        rpm = re.search(r"\bSpeed:\s*(-?\d+(?:\.\d+)?)f", nbt)
        phase = re.search(r'\bState:\s*"([A-Z]+)"', nbt)
        timer = re.search(r"\bTimer:\s*(-?\d+)", nbt)
        items = re.search(r"\bItems:\s*(\[[^\]]*\])", nbt)
        assert rpm and items, nbt
        held = re.search(r"\bcount:\s*(\d+)", items[1])
        actual.append({
            "tick": expected["tick"],
            "scenario": expected["scenario"],
            "rpm": str(int(float(rpm[1]))),
            "phase": phase[1] if phase else "WAITING",
            "timer": timer[1] if timer else "0",
            "held": held[1] if held else "0",
            "target": target["state"],
        })
    return actual


def run(args):
    expected = reference("timing")
    seen = []
    lanes = [(9, 172, 16 + 4 * index) for index in range(len(reference("setup")))]
    end = int(expected[-1]["tick"])
    mode = "LAN" if args.lan else "Solo"
    env = {"HORIZON_NO_AUDIO": "1"}
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, f"DeployerApplication{mode}", pack=args.pack, env=env))
        actor = host
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            name = "DeployAppGuest"
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-deploy-")))
            actor = stack.enter_context(mp.joined_client(args, scratch, f"127.0.0.1:{port}", name,
                                                         scenario="deployer-applications", pack=args.pack, env=env))
            mp.until("the guest to join", lambda: any(guest["name"] == name and guest["placed"]
                     for guest in host.call("lan", "status")["guests"]))
            host.command(f"/tp {name} 13.5 172 22.5")
        host.command("/tp @s 13.5 172 22.5")
        setup(host, lanes)
        start = host.clock()
        for tick in range(end + 1):
            if tick:
                host.step_to(start + tick)
            rows = [row for row in expected if int(row["tick"]) == tick]
            seen.extend(inspect(host, lanes, rows))
            if args.lan and tick in (0, 10):
                for (x, y, z), row in zip(lanes, rows, strict=True):
                    mp.until(f"the guest to see {row['scenario']} at tick {tick}", lambda:
                             actor.call("block", x + 2, y, z)["state"] == row["target"], seconds=5)
            assert host.clock() == start + tick
    output = ROOT / ".local" / f"deployer-applications-{mode.lower()}-horizon.csv"
    with output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=expected[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(seen)
    mismatches = [(want, got) for want, got in zip(expected, seen, strict=True) if want != got]
    assert not mismatches, f"{len(mismatches)} snapshots differed; first three {mismatches[:3]}. See {output}"
    print(f"{mode}: six Deployer lanes matched Java across {end + 1} ticks, including bound-cardboard axis retention.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())
