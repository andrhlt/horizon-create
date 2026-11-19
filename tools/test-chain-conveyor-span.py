#!/usr/bin/env python3
"""Remove the original conveyor spans with a survival wrench click in an isolated headless world."""

import argparse
import csv
import importlib
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


chain = importlib.import_module("test-chain-conveyor-packages")
kinetics = importlib.import_module("test-chain-conveyor-kinetics")
multiplayer = importlib.import_module("test-multiplayer")
BOX = "create:cardboard_package_12x12"
WRENCH = "create:wrench"
IRON_CHAIN = "minecraft:iron_chain"
A = (8, 102, -10)


def coords(at):
    return " ".join(map(str, at))


def exists(host, at):
    return "[I;" in host.command(f"/data get block {coords(at)} Connections")


def box_data(host, target):
    return host.command(f"/data get entity {target} equipment.mainhand").partition("entity data: ")[2]


def checked_connection(scenario):
    with (ROOT / "fixtures/chain-conveyor-connection-java.csv").open() as rows:
        return next(row for row in csv.DictReader(rows)
                    if row["scenario"] == scenario and row["action"] == "disconnected")


def verify(host, actor, name, scenario, a, b, offset, offhand=False):
    expected = checked_connection(scenario)
    connected = all(exists(host, at) for at in (a, b))
    assert connected and kinetics.speeds(host, (a, b)) == (128.0, 128.0)
    slot = "weapon.offhand" if offhand else "hotbar.0"

    def holds_wrench():
        if not offhand:
            return multiplayer.count(actor, WRENCH) == 1
        return WRENCH in host.command(f"/data get entity {name} equipment.offhand")

    host.commands((
        f"/gamemode survival {name}",
        f"/item replace entity {name} {slot} with {WRENCH}",
        f"/item replace entity {name} hotbar.1 with {IRON_CHAIN} 8",
    ))
    multiplayer.until("the wrench and starting chain to reach the player", lambda:
        holds_wrench() and multiplayer.count(actor, IRON_CHAIN) == 8)
    if not offhand:
        actor.call("select", WRENCH)
    for pos, direction, position, address, cargo, count in (
        (a, offset, 2.0, "Removed-A", "paper", 3),
        (b, tuple(-d for d in offset), 1.5, "Removed-B", "string", 2),
    ):
        box = chain.stack(address, cargo, count)
        edge = chain.emit_vector(direction)
        chain.merge(host, pos, f"{{Packages:[{{Item:{box},Position:{position}f,Connection:{edge}}}]}}")

    if scenario == "straight":
        place = (12.0, 103.0, -6.25)
        point = (12.0, 102.375, -8.783)
    else:
        place = (11.5, 104.0, -4.5)
        point = (11.1793, 103.375, -7.3587)
    host.command(f"/tp {name} {coords(place)}")
    multiplayer.until("player to reach the wrench position", lambda:
        actor.call("state")["player"]["position"] == list(place))
    actor.call("key", "shift", "down")
    try:
        actor.call("wait", 3)
        actor.call("look-at", *point)
        aim = actor.call("state")["looking_at"]
        assert aim["kind"] != "block" or aim["block"]["pos"] not in (list(a), list(b)), aim
        result = actor.call("use-item")
        multiplayer.until("both conveyor links removed by a click on the span", lambda:
            not any(exists(host, at) for at in (a, b)))
        after = int(expected["inventory_chains"])
        multiplayer.until("the Java chain refund to reach the inventory",
                          lambda: multiplayer.count(actor, IRON_CHAIN) == after)
        assert kinetics.speeds(host, (a, b)) == (128.0, 0.0), result
        assert holds_wrench()
        assert all("create:package_contents" not in host.command(
            f"/data get block {coords(at)} Packages") for at in (a, b))

        def boxes(peer):
            return peer.call("entities", 8, "create:package")["entities"]

        with (ROOT / "fixtures/chain-conveyor-wrench-java.csv").open() as rows:
            drops = {row["payload"]: tuple(float(row[key]) for key in "xyz")
                     for row in csv.DictReader(rows) if row["scenario"] == scenario}
        for wanted, pos in drops.items():
            label = wanted.split(":")[0]
            selector = ('@e[type=create:package,limit=1,nbt={equipment:{mainhand:{components:'
                        '{"create:package_address":"' + label + '"}}}}]')
            tag = box_data(host, selector)
            assert tag and chain.payload(tag) == wanted, (wanted, tag, boxes(host))
            actual = host.command(f"/data get entity {selector} Pos").partition("entity data: ")[2]
            relative = tuple(float(value.strip().removesuffix("d")) - base
                             for value, base in zip(actual.strip("[]").split(","), a, strict=True))
            assert all(abs(actual - java) < 2e-8 for actual, java in zip(relative, pos)), (
                wanted, relative, pos,
            )

        if actor is not host:
            host.step_to(host.clock() + 1)
        for peer in (host,) if actor is host else (host, actor):
            role = "host" if peer is host else "guest"
            try:
                multiplayer.until(f"both carried packages to reach the {role}", lambda: len(boxes(peer)) == 2)
            except RuntimeError as exc:
                raise RuntimeError((role, peer.call("state")["player"], boxes(peer), peer.call("entities", 16))) from exc

        actor.call("use-item")
        assert multiplayer.count(actor, IRON_CHAIN) == after
    finally:
        actor.call("key", "shift", "up")
    print(f"{name} {scenario}: both links removed, {after - 8} chains refunded, both addressed boxes dropped")


def run(args):
    offsets = chain.WHEELS
    offset = offsets[args.scenario]
    b = tuple(p + d for p, d in zip(A, offset))
    role = "LAN" if args.lan else "Solo"
    if args.offhand:
        role += "Offhand"
    with fixture_world(args, f"ChainWrench-{args.scenario}-{role}", pack=args.pack) as host:
        chain.setup(host, A, b, (8, 101, -10), (17, 100, -10), offset, True)
        host.commands((
            "/fill 11 102 -7 13 102 -6 minecraft:stone",
            "/fill 10 103 -5 12 103 -4 minecraft:stone",
            "/setblock 9 103 -6 minecraft:stone",
            "/tp @s 9.5 104 -5.5",
        ))
        if not args.lan:
            verify(host, host, "@s", args.scenario, A, b, offset, args.offhand)
            return
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-conveyor-wrench-") as scratch:
            with multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", "SpanGuest",
                scenario=f"chain-conveyor-wrench-{args.scenario}", pack=args.pack,
            ) as guest:
                multiplayer.until("guest to enter the world", lambda: any(
                    entry["name"] == "SpanGuest" and entry["placed"]
                    for entry in host.call("lan", "status")["guests"]
                ))
                host.command("/tp @s 9.5 104 -5.5")
                multiplayer.until("host to be in sight of the span", lambda:
                    host.call("state")["player"]["position"] == [9.5, 104.0, -5.5])
                verify(host, guest, "SpanGuest", args.scenario, A, b, offset, args.offhand)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--offhand", action="store_true")
    parser.add_argument("--scenario", choices=chain.WHEELS, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
