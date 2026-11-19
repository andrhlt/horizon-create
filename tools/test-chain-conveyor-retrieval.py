#!/usr/bin/env python3
"""Replay a right-click pickup from a wheel and from a span."""

import argparse
import csv
import importlib
from math import atan2, cos, dist, radians, sin
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


span = importlib.import_module("test-chain-conveyor-span")
player = importlib.import_module("test-chain-conveyor-player")
chain = span.chain
multiplayer = span.multiplayer
A = span.A


def get_inventory(host, name):
    message = host.command(f"/data get entity {name} Inventory")
    return chain.snbt.top_level_entries(message.partition("entity data: ")[2])


def click(host, actor, name, feet, target, *, open_air=False):
    host.command(f"/tp {name} {chain.coords(feet)}")
    multiplayer.until("player to reach the package sightline", lambda:
                      dist(actor.call("state")["player"]["position"], feet) < 0.001)
    actor.call("look-at", *target)
    if open_air:
        hit = actor.call("state")["looking_at"]
        assert hit["kind"] == "none", hit
    return actor.call("use-item")


def verify(host, actor, name, scenario, b, edge, *, open_air):
    with (ROOT / "fixtures/chain-conveyor-retrieval-java.csv").open() as stream:
        poses = {row["path"]: row for row in csv.DictReader(stream) if row["scenario"] == scenario}
    host.command(f"/gamemode survival {name}")
    player.equip(host, actor, name, "minecraft:stick", "minecraft:stick")
    host.command(f"/clear {name}")
    x, y, z = b
    angle = float(poses["loop"]["position"])
    cargo = chain.stack(poses["loop"]["address"], "paper", 3)
    loop_x = x + 0.5 + 0.875 * sin(radians(angle))
    loop_z = z + 0.5 + 0.875 * cos(radians(angle))
    identity = ",VisualId:700L" if open_air else ""
    chain.merge(host, b, f"{{Packages:[{{Item:{cargo},Position:{angle}f{identity}}}]}}")
    if open_air:
        # A level ray two blocks down from the wheel crosses only the
        # package's hitbox, even though the game reports a crosshair miss.
        host.command(f"/fill {x-4} {y-3} {z+1} {x-1} {y-3} {z+1} minecraft:stone")
        click(host, actor, name, (x - 2.0, float(y - 2), z + 1.5),
              (loop_x, y - 0.38, loop_z), open_air=True)
    else:
        # A wall behind the package routes the click through LAN UseItemOn.
        host.command(f"/fill {x-4} {y-1} {z+1} {x-1} {y-1} {z+1} minecraft:stone")
        host.command(f"/fill {x+1} {y-1} {z} {x+1} {y+1} {z+1} minecraft:stone")
        click(host, actor, name, (x - 2.0, float(y), z + 1.5), (loop_x, y - 0.18, loop_z))
    multiplayer.until("the loop package to reach the hand", lambda:
                      multiplayer.count(actor, player.PACKAGE) == 1)
    received = get_inventory(host, name)
    box = next(item for item in received if "Inventory" in item)
    assert chain.payload(box) == "Inventory:paper:3" and chain.scalar(box, "Slot") == "0", received
    assert "Inventory" not in player.get(host, b, "Packages")

    host.command(f"/clear {name}")
    player.equip(host, actor, name, "minecraft:stick", "minecraft:stick")
    progress = float(poses["span"]["position"])
    cargo = chain.stack(poses["span"]["address"], "string", 2)
    vector = tuple(-axis for axis in edge)
    direction = atan2(vector[0], vector[2])
    start_angle = direction - radians(35)
    end_angle = direction + radians(215)
    start = (x + 0.5 + 1.25 * sin(start_angle), y + 0.375, z + 0.5 + 1.25 * cos(start_angle))
    end = (A[0] + 0.5 + 1.25 * sin(end_angle), A[1] + 0.375, A[2] + 0.5 + 1.25 * cos(end_angle))
    phase = progress / dist(start, end)
    on_span = tuple(p + (q - p) * phase for p, q in zip(start, end))
    on_span = (on_span[0], on_span[1] - 9 / 16, on_span[2])
    chain.merge(host, b, f"{{Packages:[{{Item:{cargo},Position:{progress}f,Connection:[I;{','.join(map(str, vector))}]}}]}}")
    feet = (on_span[0], float(y + 1), on_span[2] + 2)
    fx, fy, fz = map(int, (feet[0], feet[1], feet[2] - 1))
    host.command(f"/fill {fx-1} {fy-1} {fz-1} {fx+1} {fy-1} {fz+2} minecraft:stone")
    click(host, actor, name, feet, on_span)
    multiplayer.until("the span package to reach the inventory", lambda:
                      multiplayer.count(actor, player.PACKAGE) == 1)
    received = get_inventory(host, name)
    box = next(item for item in received if "Pocket" in item)
    assert chain.payload(box) == "Pocket:string:2" and chain.scalar(box, "Slot") != "0", received
    assert "Pocket" not in player.get(host, b, "Packages")
    route = "open air" if open_air else "block use"
    print(f"{name} {scenario}: Java empty-hand loop via {route} and occupied-hand span retrieval")


def run(args):
    delta = chain.WHEELS[args.scenario]
    b = tuple(origin + axis for origin, axis in zip(A, delta))
    mode = "LAN" if args.lan else "Solo"
    with fixture_world(args, f"ChainRetrieval-{args.scenario}-{mode}", pack=args.pack) as host:
        chain.setup(host, A, b, (8, 101, -10), (17, 100, -10), delta, True)
        if args.open_air:
            host.command("/setblock 8 101 -10 minecraft:air")
            for tick in range(host.clock() + 1, host.clock() + 4):
                host.step_to(tick)
        if not args.lan:
            verify(host, host, "@s", args.scenario, b, delta, open_air=args.open_air)
            return
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-chain-retrieval-") as scratch:
            with multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", "RetrievalGuest",
                scenario=f"chain-retrieval-{args.scenario}", pack=args.pack,
            ) as guest:
                multiplayer.until("guest to enter the world", lambda: any(
                    entry["name"] == "RetrievalGuest" and entry["placed"]
                    for entry in host.call("lan", "status")["guests"]
                ))
                verify(host, guest, "RetrievalGuest", args.scenario, b, delta, open_air=args.open_air)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--open-air", action="store_true")
    parser.add_argument("--scenario", choices=chain.WHEELS, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
