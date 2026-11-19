#!/usr/bin/env python3
"""Compare branched conveyor routing and custody at both original Frogports."""

import argparse
from collections import defaultdict
from contextlib import ExitStack
import csv
import importlib
from pathlib import Path
from struct import pack
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


outbound = importlib.import_module("test-chain-conveyor-outbound")
chain, player = outbound.chain, outbound.player
multiplayer = importlib.import_module("test-multiplayer")
A, B, EAST = outbound.A, outbound.B, outbound.PORT
C = (8, 102, -3)
SOUTH = (10, 100, -3)


def data(world, position, key=""):
    return world.command(f"/data get block {chain.coords(position)} {key}".rstrip()).partition("block data: ")[2]


def receipt(response):
    if "ReceivingPackage:" in response:
        return "animation:" + chain.payload(response.partition("ReceivingPackage:")[2])
    if "create:package_contents" in response:
        return "inventory:" + chain.payload(response)
    return "-"


def load_from_players(world, guest, name, east, south):
    supply = (7, 100, -11)
    world.command(f"/setblock {chain.coords(supply)} minecraft:barrel")
    chain.merge(world, supply, "{Items:[{Slot:0b," + east[1:] + ",{Slot:1b," + south[1:] + "]}")
    world.command("/fill 10 100 -8 12 100 -6 minecraft:stone")
    world.command("/setblock 11 100 -10 minecraft:stone")
    for slot, actor, operator in ((0, world, "@s"), (1, guest, name)):
        world.command(f"/gamemode survival {operator}")
        world.command(f"/item replace entity {operator} hotbar.0 from block {chain.coords(supply)} container.{slot}")
        multiplayer.until("the operator to receive an addressed box", lambda:
                          multiplayer.count(actor, player.PACKAGE) == 1)
        actor.call("select", player.PACKAGE)
        player.select_loop(world, actor, operator, A, (1, 1))
        multiplayer.until("the addressed box to leave the operator's hand", lambda:
                          multiplayer.count(actor, player.PACKAGE) == 0)
        if actor is world:
            world.command("/tp @s 11.5 101 -9.5")


def remove_relay(world, actor, name, side):
    world.commands((
        f"/gamemode survival {name}",
        "/setblock 12 101 -6 minecraft:stone",
        f"/item replace entity {name} hotbar.1 with minecraft:iron_chain 8",
    ))
    player.equip(world, actor, name, "create:wrench", "create:wrench")
    world.command(f"/tp {name} 12.5 102 -5.5")
    multiplayer.until("the operator to reach the relay", lambda:
                      actor.call("state")["player"]["position"] == [12.5, 102, -5.5])
    actor.call("key", "shift", "down")
    try:
        actor.call("wait", 3)
        actor.call("look-at", 14.783, 102.375, -6)
        actor.call("use-item")
        multiplayer.until("the wrench to detach the relay span", lambda:
                          "[I;" not in data(world, side, "Connections"))
    finally:
        actor.call("key", "shift", "up")
    multiplayer.until("the Java chain refund to reach the operator", lambda:
                      multiplayer.count(actor, "minecraft:iron_chain") == 11)


def restore_relay(world, actor, name, side):
    actor.call("select", "minecraft:iron_chain")
    for x, y, z in (B, side):
        world.command(f"/setblock {x} {y} {z+1} minecraft:stone")
        player.click(world, actor, name, (x, y, z), (x + .5, y + 1, z + 1.5), (x + .5, y + .95, z + .5))
    multiplayer.until("the restored span to spend three chains", lambda:
                      multiplayer.count(actor, "minecraft:iron_chain") == 8)


def run(args):
    shape = "relink" if args.relink else "relay" if args.relay else "branch"
    has_relay = shape != "branch"
    fixture = f"chain-conveyor-{shape}" + ("-player" if args.lan and not args.relink else "")
    world_rows = ROOT / f"fixtures/{fixture}-world-java.csv"
    with world_rows.open() as stream:
        expected = list(csv.DictReader(stream))
    packages = defaultdict(list)
    with (ROOT / f"fixtures/{fixture}-package-java.csv").open() as stream:
        for row in csv.DictReader(stream):
            packages[int(row["tick"])].append((
                row["wheel"], row["path"], row["edge"], row["payload"],
                pack("f", float(row["chain_position"])),
            ))
    errors = []
    label = "ChainConveyor" + shape.title() + ("LAN" if args.lan else "")
    side, side_port = ((15, 102, -3), (17, 100, -3)) if has_relay else (C, SOUTH)
    with ExitStack() as stack:
        world = stack.enter_context(fixture_world(args, label, pack=args.pack))
        guest, name = None, "BranchGuest"
        if args.lan:
            address = "127.0.0.1:" + str(world.call("lan", "open", "0", "commands", "force")["port"])
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-chain-branch-")))
            guest = stack.enter_context(multiplayer.joined_client(
                args, scratch, address, name, scenario="chain-branch", pack=args.pack,
            ))
            multiplayer.until("guest to enter the conveyor world", lambda: any(
                player["name"] == name and player["placed"]
                for player in world.call("lan", "status")["guests"]
            ))
        chain.setup(world, A, B, (8, 101, -10), EAST, (7, 0, 0), False, warm=0)
        world.command(f"/setblock {chain.coords(side)} create:chain_conveyor")
        world.command(f"/setblock {chain.coords(side_port)} create:package_frogport")
        if has_relay:
            chain.merge(world, B, "{Connections:[[I;-7,0,0],[I;0,0,7]]}")
        else:
            chain.merge(world, A, "{Connections:[[I;7,0,0],[I;0,0,7]]}")
        chain.chain.set_link(world, side, (0, 0, -7))
        warm = world.clock()
        for step in range(1, 4):
            world.step_to(warm + step)
        for wheel, port, address in ((B, EAST, "Lab-In"), (side, side_port, "Side")):
            chain.merge(world, port, f'{{AddressFilter:"{address}",Target:{{RelativePos:[I;-2,2,0],ChainPosition:150f}}}}')
            chain.merge(world, wheel, "{PackagePorts:[{Port:[I;2,-2,0],ChainPosition:150f}]}")
        start = world.clock()
        for tick, row in enumerate(expected):
            if tick:
                world.step_to(start + tick)
            if args.relink and tick == 10:
                remove_relay(world, guest or world, name if guest else "@s", side)
            if args.relink and tick == 112:
                restore_relay(world, guest or world, name if guest else "@s", side)
            if tick == 2:
                east = chain.stack("Lab-In", "paper", 3)
                south = chain.stack("Side", "string", 2)
                if guest and not args.relink:
                    load_from_players(world, guest, name, east, south)
                else:
                    chain.merge(world, A, f"{{Packages:[{{Item:{east},Position:40f}},{{Item:{south},Position:40f}}]}}")
            queries = (
                *(f"/data get block {chain.coords(pos)}" for pos in (side, EAST, side_port)),
                f"/data get block {chain.coords(A)} RoutingEntries",
                *(f"/data get block {chain.coords(pos)} Packages" for pos in (A, B, side)),
                *((f"/data get block {chain.coords(B)} RoutingEntries",) if has_relay else ()),
            )
            state = world.commands(queries)
            c, east, south, routing, *tail = [reply.partition("block data: ")[2] for reply in state]
            assert all((c, east, south)), state
            entries = list(chain.snbt.top_level_entries(routing))
            routes = {
                address: next((chain.field_vector(entry, "Next") for entry in entries if f'"{address}"' in entry),
                              "0:0:0")
                for address in ("Lab-In", "Side")
            }
            actual = (
                routes["Lab-In"], routes["Side"], float(chain.scalar(c, "Speed")),
                *(value for port in (east, south) for value in (
                    pack("f", float(chain.scalar(port, "AnimationProgress"))), receipt(port),
                )),
            )
            wanted = (
                row["east_route"], row["south_route"], float(row["side_rpm"]),
                *(value for label in ("east", "south") for value in (
                    pack("f", float(row[label + "_progress"])), row[label + "_custody"],
                )),
            )
            if has_relay:
                entries = chain.snbt.top_level_entries(tail[3])
                actual += (next((chain.field_vector(entry, "Next") for entry in entries
                                 if '"Side"' in entry), "0:0:0"),)
                wanted += (row["relay_route"],)
            if actual != wanted:
                errors.append(f"tick {tick} route/port actual {actual!r}, Java {wanted!r}")
            cargo = []
            for label, saved in zip(("A", "B", "C"), tail[:3], strict=True):
                for entry in chain.snbt.top_level_entries(saved):
                    edge = chain.field_vector(entry, "Connection")
                    cargo.append((label, "loop" if edge == "-" else "travel", edge, chain.payload(entry),
                                  pack("f", float(chain.scalar(entry, "Position")))))
            if sorted(cargo) != sorted(packages[tick]):
                errors.append(f"tick {tick} cargo actual {cargo!r}, Java {packages[tick]!r}")
            if len(errors) >= 16:
                break
    if errors:
        raise AssertionError("\n".join(errors))
    print(f"{len(expected)} Java {shape} ticks and {sum(map(len, packages.values()))} package states")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--lan", action="store_true")
    shapes = parser.add_mutually_exclusive_group()
    shapes.add_argument("--relay", action="store_true")
    shapes.add_argument("--relink", action="store_true")
    run(parser.parse_args())
