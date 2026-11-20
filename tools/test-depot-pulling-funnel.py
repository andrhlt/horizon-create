#!/usr/bin/env python3
"""Replay original stationary Depot output through a Pulling Belt Funnel."""
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
BARRELS = (6, 6, 6)
HEADER = "rig,tick,depot,barrel,powered"
BLOCKED_ITEMS = '[{Slot:0b,id:"minecraft:iron_ingot",count:63},' + ",".join(
    f'{{Slot:{slot}b,id:"minecraft:stone",count:64}}' for slot in range(1, 27)
) + "]"


def setup(host):
    commands = []
    for rig, z in enumerate(Z):
        commands.extend((
            f"/fill 2 103 {z-2} 12 103 {z+2} minecraft:smooth_stone",
            f"/fill 2 104 {z-2} 12 111 {z+2} minecraft:air",
            f"/setblock 5 104 {z} create:depot",
            f"/setblock 6 105 {z} minecraft:barrel",
            f"/setblock 5 105 {z} create:brass_belt_funnel[facing=west,shape=pulling]",
        ))
        if rig == 1:
            commands.append(f"/setblock 5 106 {z} minecraft:redstone_block")
        if rig == 2:
            commands.append(f"/data merge block 6 105 {z} {{Items:{BLOCKED_ITEMS}}}")
    commands.extend(("/gamemode spectator @s", "/tp @s 8.5 105 -10.5"))
    host.call("script", script="".join(f"command {json.dumps(command)}\n" for command in commands))


def contents(reply):
    return sum(launch.count(entry) for entry in re.findall(r"\{[^{}]+\}", reply))


def tick(host, tick):
    if tick == 12:
        host.commands(f'/data merge block 5 104 {z} {{Items:[{{Slot:0b,id:"{IRON}",count:3}}],BeltPosition:0.5f}}'
                      for z in Z)
    if tick == 18:
        host.call("command", "/setblock 5 106 -5 minecraft:air")
    if tick == 20:
        host.call("command", "/data merge block 6 105 1 {Items:[]}")
    replies = host.commands(command for z in Z for command in (
        f"/data get block 5 104 {z} Items", f"/data get block 6 105 {z} Items",
    ))
    for rig, z in enumerate(Z):
        depot, barrel = replies[rig * 2 : rig * 2 + 2]
        powered = re.search(r"owered=(true|false)", host.call("block", 5, 105, z)["state"])
        yield [str(rig), str(tick), str(contents(depot)), str(contents(barrel)), powered[1]]


def active_reopen(host):
    z = 10
    host.commands((
        f"/fill 2 103 {z-2} 12 103 {z+2} minecraft:smooth_stone",
        f"/fill 2 104 {z-2} 12 111 {z+2} minecraft:air",
        f"/setblock 5 104 {z} create:depot",
        f"/setblock 6 105 {z} minecraft:barrel",
        f"/setblock 5 105 {z} create:brass_belt_funnel[facing=west,shape=pushing]",
        f'/data merge block 5 105 {z} {{Filter:{{id:"{IRON}",count:1}},FilterAmount:2,UpTo:0b}}',
        f'/data merge block 6 105 {z} {{Items:[{{Slot:0b,id:"{IRON}",count:5}}]}}',
    ))

    def counts():
        source, depot = host.commands((
            f"/data get block 6 105 {z} Items",
            f"/data get block 5 104 {z} Items",
        ))
        return contents(source), contents(depot)

    def settings():
        filter_data, amount, up_to = host.commands((
            f"/data get block 5 105 {z} Filter",
            f"/data get block 5 105 {z} FilterAmount",
            f"/data get block 5 105 {z} UpTo",
        ))
        assert IRON in filter_data and amount.endswith("2") and up_to.endswith("0b"), (
            filter_data, amount, up_to,
        )

    host.step_to(host.clock() + 1)
    assert counts() == (3, 2), f"Exact-two transfer did not conserve the five-item source: {counts()}"
    settings()
    host.call("save")
    host.restart()
    assert counts() == (3, 2), f"Active save/reopen changed Funnel custody: {counts()}"
    settings()

    start = host.clock()
    for tick in range(1, 31):
        host.step_to(start + tick)
        if host.command(f"/data get block 5 105 {z} TransferCooldown").endswith("0"):
            break
    assert counts() == (3, 2), f"Occupied Depot should apply backpressure after reopen: {counts()}"
    settings()

    host.command(f"/data merge block 5 104 {z} {{Items:[]}}")
    start = host.clock()
    for tick in range(1, 12):
        host.step_to(start + tick)
        if counts() == (1, 2):
            break
    assert counts() == (1, 2), f"Exact-count transfer did not resume after output cleared: {counts()}"
    settings()
    host.command(f"/setblock 5 106 {z} minecraft:redstone_block")
    host.step_to(host.clock() + 1)
    host.call("save")
    host.restart()
    assert counts() == (1, 2), f"Idle save/reopen changed Funnel custody: {counts()}"
    assert "powered=true" in host.call("block", 5, 105, z)["state"]
    settings()
    host.command(f"/setblock 5 106 {z} minecraft:air")
    start = host.clock()
    for tick in range(1, 12):
        host.step_to(start + tick)
        if "powered=false" in host.call("block", 5, 105, z)["state"]:
            break
    assert counts() == (1, 2), f"One-item remainder was lost after resuming: {counts()}"
    print("Active and idle save/reopen retained the exact-two filter, backpressure, and transfer custody.")


def main():
    parser = ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/depot-pulling-funnel-java.csv")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--reopen", action="store_true")
    args = parser.parse_args()
    with args.reference.open() as source:
        rows = csv.reader(source)
        assert ",".join(next(rows)) == HEADER
        expected = list(rows)
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "DepotPullingFunnel", render=True, pack=args.pack))
        setup(host)
        guest = None
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-ejf-")))
            guest = stack.enter_context(mp.joined_client(
                args, scratch, f"127.0.0.1:{port}", "FunnelGuest", render=True,
                scenario="depot-pulling-funnel", pack=args.pack,
            ))
            mp.until("the Ejector Funnel operator joins", lambda: any(
                p["name"] == "FunnelGuest" and p["placed"] for p in host.call("lan", "status")["guests"]
            ))
        start = host.clock()
        actual = []
        for logical in range(1, 33):
            host.step_to(start + logical)
            actual.extend(tick(host, logical))
        if args.output:
            with args.output.open("w") as file:
                print(HEADER, file=file)
                csv.writer(file).writerows(actual)
        if actual != expected:
            mismatches = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
            raise RuntimeError(f"{len(mismatches)} mismatching Depot funnel rows (Java, Horizon): {mismatches[:8]}")
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
                    and slot["stack"]["count"] == (2 if index == 3 else 3) for slot in guest.call("menu").get("slots", [])
                ))
                guest.call("click-slot", 300, "shift")
                host.step_to(host.clock() + 1)
                mp.until("guest collects the barrel output", lambda: mp.count(guest, IRON) == (8 if index == 3 else 3 * index))
                guest.call("close")
        if args.reopen:
            active_reopen(host)
    print(f"Matched {len(actual)} Java tick rows across three Funnel rigs.")


if __name__ == "__main__":
    main()
