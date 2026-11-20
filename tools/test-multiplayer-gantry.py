#!/usr/bin/env python3
"""Check gantry operation from a guest and preserve idle/moving saves."""

import argparse
from importlib import import_module
from math import floor
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

multiplayer = import_module("test-multiplayer")
BASE = (3, 96, -12)
TEMPLATE = Path("gametest/contraptions/roller_filling.nbt")
LEVER = (BASE[0] + 7, BASE[1] + 5, BASE[2] + 1)
GANTRY = "@e[type=minecraft:marker,tag=create_gantry_payload,limit=1]"
GUEST = "GantryGuest"


def read_offset(client):
    report = client.command(f"/data get entity {GANTRY} CreateGantry.Offset")
    match = re.search(r"(-?\d+(?:\.\d+)?)d", report)
    return float(match[1]) if match else None


def vector(client, key):
    report = client.command(f"/data get entity {GANTRY} CreateGantry.{key}")
    match = re.search(r"\[I;([^\]]+)\]", report)
    return tuple(map(int, re.findall(r"-?\d+", match[1]))) if match else None


def drive_report(client, offset):
    origin = vector(client, "Origin")
    axis = vector(client, "Axis")
    support = vector(client, "Support")
    if not (origin and axis and support):
        return client.command(f"/data get entity {GANTRY} CreateGantry")
    carriage = tuple(floor(start + direction * offset + 0.5)
                     for start, direction in zip(origin, axis, strict=True))
    shaft = tuple(at + delta for at, delta in zip(carriage, support, strict=True))
    position = " ".join(map(str, shaft))
    states = client.call("blocks", 1, 94, -15, 16, 111, -5)["blocks"]
    kinetic = [(x, y, z, state.split("[", 1)[0]) for x, y, z, state in states
               if any(name in state for name in ("shaft", "gearbox", "gearshift", "motor", "cogwheel"))]
    reports = client.commands(f"/data get block {x} {y} {z} Speed" for x, y, z, _ in kinetic)
    return (f"shaft={shaft} {client.call('block', *shaft)['state']} "
            f"{client.command(f'/data get block {position} Speed')} kinetic={list(zip(kinetic, reports, strict=True))}")


def advance(client, ticks):
    for _ in range(ticks):
        client.step_to(client.clock() + 1)


def require_carriage(client):
    x, y, z = BASE
    block = client.call("block", x + 6, y + 5, z + 2)["block"]
    if not block.startswith("create:gantry_carriage"):
        raise RuntimeError(f"Idle gantry carriage was not retained: {block}")


def run(args, scratch):
    x, y, z = BASE
    lx, ly, lz = LEVER
    with fixture_world(args, "Gantry-LAN-reload", TEMPLATE, render=True, pack=args.pack) as host:
        host.command(f"/place template create:{TEMPLATE.with_suffix('')} {x} {y} {z}")
        host.command(f"/setblock {lx} {ly} {lz} minecraft:lever[face=wall,facing=north,powered=true]")
        host.command(f"/tp @s {x + 8.5} {y + 3} {z - 2.5}")
        advance(host, 4)
        if read_offset(host) is not None:
            raise RuntimeError("Gantry assembled while its shaft was powered")
        require_carriage(host)

        host.restart()
        if read_offset(host) is not None:
            raise RuntimeError("An idle gantry assembled during save/reopen")
        require_carriage(host)

        session = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{session['port']}"
        with multiplayer.joined_client(args, scratch, address, GUEST, render=True,
                                       scenario="gantry-lan-reload") as guest:
            multiplayer.until("the guest to join the gantry world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.command(f"/gamemode survival {GUEST}")
            host.command(f"/tp {GUEST} {lx + 0.5} {ly + 1.0} {lz - 2.5}")
            multiplayer.until("the guest to reach the gantry control", lambda:
                guest.call("state")["gamemode"] == "survival"
                and guest.call("state")["player"]["position"] == [lx + 0.5, ly + 1.0, lz - 2.5]
            )
            multiplayer.until("the guest to see the gantry lever", lambda:
                guest.call("block", lx, ly, lz)["state"].startswith("minecraft:lever")
            )
            guest.call("interact", lx, ly, lz)
            advance(host, 1)
            lever = host.call("block", lx, ly, lz)["state"]
            if "powered=false" not in lever:
                raise RuntimeError(f"Guest did not switch on the gantry drive: {lever}")

            for _ in range(8):
                advance(host, 1)
            host_offset = read_offset(host)
            if host_offset is None or host_offset <= 0:
                raise RuntimeError(f"Guest-powered gantry did not start moving: {host_offset}")
            multiplayer.until("the guest to observe the moving gantry", lambda:
                "powered=false" in guest.call("block", lx, ly, lz)["state"]
                and guest.call("block", x + 6, y + 5, z + 2)["block"] == "minecraft:air"
            )

        saved_offset = read_offset(host)
        if saved_offset is None:
            raise RuntimeError("The moving gantry disappeared before its save")
        host.restart()
        restored_offset = read_offset(host)
        if restored_offset is None or restored_offset + 1e-9 < saved_offset:
            raise RuntimeError(f"Moving gantry save lost progress: {saved_offset} -> {restored_offset}")
        advance(host, 3)
        resumed_offset = read_offset(host)
        if resumed_offset is None or max(restored_offset, resumed_offset) <= saved_offset:
            raise RuntimeError(f"Moving gantry did not resume after reopen: {saved_offset} -> "
                               f"{restored_offset} -> {resumed_offset}; "
                               f"{drive_report(host, restored_offset)}")

    print("A LAN guest started the gantry; idle and moving save/reopen retained state and motion resumed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    with TemporaryDirectory(prefix="hc-gantry-lan-") as scratch:
        run(parser.parse_args(), Path(scratch))
