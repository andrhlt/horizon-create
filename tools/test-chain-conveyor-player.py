#!/usr/bin/env python3
"""Verify survival players can bind a Frogport and load a package through actual use clicks."""

import argparse
import csv
import importlib
from pathlib import Path
from struct import pack
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


chain = importlib.import_module("test-chain-conveyor-packages")
multiplayer = importlib.import_module("test-multiplayer")
A = (8, 102, -10)
B = (15, 102, -10)
PORT = (17, 100, -10)
SUPPORT = (17, 99, -10)
PORT_ITEM = "create:package_frogport"
PACKAGE = "create:cardboard_package_12x12"


def get(host, at, key):
    return host.command(f"/data get block {chain.coords(at)} {key}").partition("block data: ")[2]


def click(host, actor, name, at, position, point):
    host.command(f"/tp {name} {chain.coords(position)}")
    multiplayer.until("player to reach the click position", lambda:
        actor.call("state")["player"]["position"] == list(position))
    actor.call("look-at", *point)
    aim = actor.call("state")["looking_at"]
    assert aim["kind"] == "block" and aim["block"]["pos"] == list(at), aim
    return actor.call("use-item")


def select_loop(host, actor, name, at, signs):
    x, y, z = at
    dx, dz = signs
    return click(host, actor, name, at, (x + 0.5 + dx * 2.5, y - 1.0, z + 0.5 + dz * 2.5),
                 (x + 0.5, y + 0.25, z + 0.5))


def equip(host, actor, name, stack, item):
    host.command(f"/item replace entity {name} hotbar.0 with {stack}")
    multiplayer.until(f"{item} to reach the inventory", lambda: multiplayer.count(actor, item) == 1)
    actor.call("select", item)


def verify(host, actor, name):
    with (ROOT / "fixtures/chain-conveyor-player-java.csv").open() as rows:
        expected = list(csv.DictReader(rows))
    port_angle = expected[0]["port_angle"]
    host.command(f"/gamemode survival {name}")
    equip(host, actor, name, PORT_ITEM, PORT_ITEM)
    selected = select_loop(host, actor, name, B, (1, -1))
    assert multiplayer.count(actor, PORT_ITEM) == 1, selected
    click(host, actor, name, SUPPORT, (17.5, 100.0, -7.5), (17.5, 99.99, -9.5))
    multiplayer.until("the placed Frogport to bind to the second conveyor",
                      lambda: port_angle in get(host, PORT, "Target"))
    assert multiplayer.count(actor, PORT_ITEM) == 0
    binding = get(host, B, "PackagePorts")
    assert port_angle in binding and chain.vector(binding) == "2:-2:0", binding
    chain.merge(host, PORT, '{AddressFilter:"Lab-In"}')
    registered = host.clock()
    host.step_to(registered + 1)
    host.step_to(registered + 2)
    assert "Lab-In" in get(host, A, "RoutingEntries")

    supply = (7, 100, -11)
    host.command(f"/setblock {chain.coords(supply)} minecraft:barrel")
    stack = chain.stack("Lab-In", "paper", 3)
    chain.merge(host, supply, "{Items:[{Slot:0b," + stack[1:] + "]}")
    host.command(f"/item replace entity {name} hotbar.0 from block {chain.coords(supply)} container.0")
    multiplayer.until("the addressed package to reach the inventory",
                      lambda: multiplayer.count(actor, PACKAGE) == 1)
    actor.call("select", PACKAGE)
    selected = select_loop(host, actor, name, A, (1, 1))
    multiplayer.until("the package to transfer out of the player's hand",
                      lambda: multiplayer.count(actor, PACKAGE) == 0)
    start = host.clock()
    events = {}
    for wanted in expected:
        tick = int(wanted["tick"])
        if tick:
            host.step_to(start + tick)
        replies = host.commands((
            f"/data get block {chain.coords(A)} Packages",
            f"/data get block {chain.coords(B)} Packages",
            f"/data get block {chain.coords(PORT)} ReceivingPackage",
            f"/data get block {chain.coords(PORT)} Items",
            f"/data get block {chain.coords(PORT)} AnimationProgress",
        ))
        source, dest, receive, items, progress = [reply.partition("block data: ")[2] for reply in replies]
        span = chain.field_vector(source or dest, "Connection")
        active = source or dest
        path = "travel" if span != "-" else "loop" if active else "-"
        wheel = "A" if source else "B" if dest else "-"
        position = pack("f", float(chain.scalar(active, "Position"))) if active else None
        expected_pos = pack("f", float(wanted["position"])) if wanted["position"] != "-" else None
        assert (wheel, path, span, position) == (wanted["wheel"], wanted["path"], wanted["edge"], expected_pos), (
            tick, selected, source, dest, wanted,
        )
        if active:
            assert chain.payload(active) == "Lab-In:paper:3", active
        custody = "-"
        if receive:
            custody = "animation:" + chain.payload(receive)
        elif "create:package_contents" in items:
            custody = "inventory:" + chain.payload(items)
        assert custody == wanted["custody"] and abs(float(progress.removesuffix("f") or 0.0) - float(wanted["progress"])) < 1e-7, (
            tick, custody, progress, wanted,
        )
        for event, present in (
            ("span", path == "travel"),
            ("destination", wheel == "B"),
            ("catch", custody.startswith("animation:")),
            ("inventory", custody.startswith("inventory:")),
        ):
            if present:
                events.setdefault(event, tick)
    print(f"{name}: {len(expected)} Java delivery ticks, {port_angle}-degree Frogport binding, {events}")


def run(args):
    role = "LAN" if args.lan else "Solo"
    with fixture_world(args, f"ChainDeliveryPlayer-{role}", pack=args.pack) as host:
        chain.setup(host, A, B, (8, 101, -10), PORT, (7, 0, 0), True)
        host.commands((
            "/fill 6 99 -14 21 99 -6 minecraft:stone",
            "/fill 17 100 -13 18 100 -11 minecraft:stone",
            "/fill 10 100 -9 11 100 -7 minecraft:stone",
        ))
        if not args.lan:
            verify(host, host, "@s")
            return
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-conveyor-delivery-") as scratch:
            with multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", "DeliveryGuest",
                scenario="chain-conveyor-delivery", pack=args.pack,
            ) as guest:
                multiplayer.until("guest to enter the world", lambda: any(
                    entry["name"] == "DeliveryGuest" and entry["placed"]
                    for entry in host.call("lan", "status")["guests"]
                ))
                verify(host, guest, "DeliveryGuest")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--lan", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
