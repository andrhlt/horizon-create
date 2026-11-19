#!/usr/bin/env python3
"""Compare Brass Pulling Funnel diversion from the Weighted Ejector."""
from argparse import ArgumentParser
from contextlib import ExitStack
import csv
from importlib import import_module
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
launch = import_module("test-depot-ejector-launch")
Z = (-11, -5, 1)
IRON = "minecraft:iron_ingot"
BARRELS = (6, 6, 4)
HEADER = "rig,tick,state,held,flying,barrel,depot,shape"
BLOCKED_ITEMS = '[{Slot:0b,id:"minecraft:iron_ingot",count:63},' + ",".join(
    f'{{Slot:{slot}b,id:"minecraft:stone",count:64}}' for slot in range(1, 27)
) + "]"


def setup(host):
    commands = []
    for rig, z in enumerate(Z):
        commands.extend((
            f"/fill 2 103 {z-2} 12 103 {z+2} minecraft:smooth_stone",
            f"/fill 2 104 {z-2} 12 111 {z+2} minecraft:air",
            f"/setblock 4 104 {z} minecraft:redstone_block",
            f"/setblock 5 104 {z} create:weighted_ejector[facing=east]{{HorizontalDistance:4,VerticalDistance:0}}",
            f"/setblock 5 104 {z-1} create:creative_motor[facing=south]{{ScrollValue:128}}",
            f"/setblock 9 104 {z} create:depot",
            f"/setblock {BARRELS[rig]} 105 {z} minecraft:barrel",
            f"/setblock 5 105 {z} create:brass_belt_funnel[facing={'east' if rig == 2 else 'west'},shape=pulling]",
        ))
        if rig == 1:
            commands.append(f"/data merge block {BARRELS[1]} 105 {z} {{Items:{BLOCKED_ITEMS}}}")
    commands.extend(("/gamemode spectator @s", "/tp @s 8.5 105 -10.5"))
    host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in commands))


def contents(reply):
    return sum(launch.count(entry) for entry in re.findall(r"\{[^{}]+\}", reply))


def tick(host, tick):
    if tick == 12:
        host.commands(command for z in Z for command in (
            f'/data merge block 5 104 {z} {{Items:[{{Slot:0b,id:"{IRON}",count:3}}],BeltPosition:0.5f}}',
            f"/setblock 4 104 {z} minecraft:air",
        ))
    if tick == 20:
        host.call("command", "/data merge block 6 105 -5 {Items:[]}")
    replies = host.commands(command for rig, z in enumerate(Z) for command in (
        f"/data get block 5 104 {z} State", f"/data get block 5 104 {z} Items",
        f"/data get block 5 104 {z} LaunchedItems", f"/data get block {BARRELS[rig]} 105 {z} Items",
        f"/data get block 9 104 {z} Items",
    ))
    for rig, z in enumerate(Z):
        state, held, flying, barrel, depot = replies[rig * 5 : rig * 5 + 5]
        phase = re.search(r"\b(CHARGED|LAUNCHING|RETRACTING)\b", state)
        observed = re.search(r"shape=(\w+)", host.call("block", 5, 105, z)["state"])
        yield [str(rig), str(tick), phase[1], str(contents(held)), str(flying.count("Time:")),
               str(contents(barrel)), str(contents(depot)), observed[1]]


def main():
    parser = ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/weighted-ejector-funnel-java.csv")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with args.reference.open() as source:
        rows = csv.reader(source)
        assert ",".join(next(rows)) == HEADER
        expected = list(rows)
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "EjectorPullingFunnel", render=True, pack=args.pack))
        setup(host)
        guest = None
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejf-")))
            guest = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", "FunnelGuest", render=True,
                scenario="ejector-pulling-funnel", pack=args.pack,
            ))
            mp.until("the Ejector Funnel operator joins", lambda: any(
                p["name"] == "FunnelGuest" and p["placed"] for p in host.call("lan", "status")["guests"]
            ))
        start = host.clock()
        actual = []
        for logical in range(1, 61):
            host.step_to(start + logical)
            actual.extend(tick(host, logical))
        if args.output:
            with args.output.open("w") as file:
                print(HEADER, file=file)
                csv.writer(file).writerows(actual)
        if actual != expected:
            mismatches = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
            raise RuntimeError(f"{len(mismatches)} mismatching Ejector funnel rows (Java, Horizon): {mismatches[:8]}")
        if guest:
            for index, (x, z) in enumerate(zip(BARRELS, Z, strict=True), 1):
                host.command(f"/setblock {x} 104 {z + 2} minecraft:smooth_stone")
                host.command(f"/tp FunnelGuest {x + .5} 105 {z + 2.5}")
                host.step_to(host.clock() + 1)
                mp.until("operator reaches the barrel", lambda:
                         guest.call("state")["player"]["position"] == [x + .5, 105, z + 2.5])
                guest.call("look-at", x + .5, 105.45, z + .5)
                guest.call("interact", x, 105, z, "south")
                mp.until("guest sees the transferred iron in the actual barrel menu", lambda: any(
                    slot["slot"] == 300 and slot.get("stack") and slot["stack"]["item"] == IRON
                    and slot["stack"]["count"] == 3 for slot in guest.call("menu").get("slots", [])
                ))
                guest.call("click-slot", 300, "shift")
                host.step_to(host.clock() + 1)
                mp.until("guest collects all three ingots from the barrel", lambda: mp.count(guest, IRON) == 3 * index)
                guest.call("close")
    print(f"Matched {len(actual)} Java tick rows across three Funnel rigs.")


if __name__ == "__main__":
    main()
