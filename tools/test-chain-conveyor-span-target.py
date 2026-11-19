#!/usr/bin/env python3
"""Select a straight or rising conveyor span with a Frogport and an addressed package."""

import argparse
import csv
import importlib
from pathlib import Path
from struct import pack
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


span = importlib.import_module("test-chain-conveyor-span")
player = importlib.import_module("test-chain-conveyor-player")
chain = span.chain
multiplayer = span.multiplayer
A = span.A
PORT = (12, 101, -5)
SUPPORT = (12, 100, -5)


def select_span(host, actor, name, scenario):
    if scenario == "straight":
        feet, point = (12.0, 103.0, -6.25), (12.0, 102.375, -8.783)
    else:
        feet, point = (11.5, 104.0, -4.5), (11.1793, 103.375, -7.3587)
    host.command(f"/tp {name} {span.coords(feet)}")
    multiplayer.until("player to reach the span sightline", lambda:
                      actor.call("state")["player"]["position"] == list(feet))
    actor.call("key", "shift", "down")
    try:
        actor.call("wait", 3)
        actor.call("look-at", *point)
        return actor.call("use-item")
    finally:
        actor.call("key", "shift", "up")


def verify(host, actor, name, scenario, b):
    with (ROOT / "fixtures/chain-conveyor-span-selection-java.csv").open() as source:
        expected = next(row for row in csv.DictReader(source) if row["scenario"] == scenario)
    expected_offset = expected["edge"]
    expected_position = pack("f", float(expected["position"]))
    owner, other = (A, b) if expected["wheel"] == "A" else (b, A)
    host.command(f"/gamemode survival {name}")
    player.equip(host, actor, name, player.PORT_ITEM, player.PORT_ITEM)
    select_span(host, actor, name, scenario)
    assert multiplayer.count(actor, player.PORT_ITEM) == 1

    player.click(host, actor, name, SUPPORT, (13.5, 101.0, -3.5), (12.5, 100.99, -4.5))
    multiplayer.until("the placed Frogport to bind to the span",
                      lambda: "Connection:" in player.get(host, PORT, "Target"))
    target = player.get(host, PORT, "Target")
    assert chain.field_vector(target, "Connection") == expected_offset, target
    assert pack("f", float(chain.scalar(target, "ChainPosition"))) == expected_position, target
    origin = tuple(p - q for p, q in zip(owner, PORT, strict=True))
    assert chain.field_vector(target, "RelativePos") == ":".join(map(str, origin)), target
    assert multiplayer.count(actor, player.PORT_ITEM) == 0
    chain.merge(host, PORT, '{AddressFilter:"Selected"}')

    supply = (7, 100, -11)
    host.command(f"/setblock {span.coords(supply)} minecraft:barrel")
    stack = chain.stack("Selected", "paper", 3)
    chain.merge(host, supply, "{Items:[{Slot:0b," + stack[1:] + "]}")
    host.command(f"/item replace entity {name} hotbar.0 from block {span.coords(supply)} container.0")
    multiplayer.until("the selected paper package to reach the hand",
                      lambda: multiplayer.count(actor, player.PACKAGE) == 1)
    actor.call("select", player.PACKAGE)
    select_span(host, actor, name, scenario)
    multiplayer.until("the conveyor to receive the held package", lambda:
                      multiplayer.count(actor, player.PACKAGE) == 0 and
                      "create:package_contents" in player.get(host, owner, "Packages"))
    loaded = player.get(host, owner, "Packages")
    assert chain.payload(loaded) == "Selected:paper:3", loaded
    assert chain.field_vector(loaded, "Connection") == expected_offset, loaded
    assert pack("f", float(chain.scalar(loaded, "Position"))) == expected_position, loaded
    assert "create:package_contents" not in player.get(host, other, "Packages")
    start = host.clock()
    host.step_to(start + 1)
    receiving = player.get(host, PORT, "ReceivingPackage")
    assert chain.payload(receiving) == "Selected:paper:3", receiving
    for tick in range(2, 11):
        host.step_to(start + tick)
    assert chain.payload(player.get(host, PORT, "Items")) == "Selected:paper:3"
    print(f"{name} {scenario}: Java span {expected['wheel']} {expected_offset} at {expected['position']}, port received package")


def run(args):
    offset = chain.WHEELS[args.scenario]
    b = tuple(p + d for p, d in zip(A, offset))
    role = "LAN" if args.lan else "Solo"
    with fixture_world(args, f"ChainSpanTarget-{args.scenario}-{role}", pack=args.pack) as host:
        chain.setup(host, A, b, (8, 101, -10), PORT, offset, True)
        host.commands((
            "/fill 11 102 -7 13 102 -6 minecraft:stone",
            "/fill 10 103 -5 12 103 -4 minecraft:stone",
            "/fill 11 100 -5 14 100 -3 minecraft:stone",
        ))
        if not args.lan:
            verify(host, host, "@s", args.scenario, b)
            return
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-span-target-") as scratch:
            with multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", "SpanTargetGuest",
                scenario=f"chain-span-target-{args.scenario}", pack=args.pack,
            ) as guest:
                multiplayer.until("guest to enter the world", lambda: any(
                    entry["name"] == "SpanTargetGuest" and entry["placed"]
                    for entry in host.call("lan", "status")["guests"]
                ))
                verify(host, guest, "SpanTargetGuest", args.scenario, b)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--scenario", choices=chain.WHEELS, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
