#!/usr/bin/env python3
"""Check the original PackageItem dropped-entity conversion using the real drop key."""
import argparse
import csv
from importlib import import_module
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
toss = import_module("test-package-throw")
GUEST = "DropGuest"
ORIGIN = (13.5, 103, 20.5)
SUPPLY = "15 103 19"
POSITION = (13.5, 103 + 1.3199999928474, 20.5)
CHUTE_SPAWN = re.compile(r"CREATE_PACKAGE_SPAWN (\d+),create:cardboard_package_12x12,([-.0-9]+),([-.0-9]+),([-.0-9]+),")
DROP = re.compile(r"CREATE_PACKAGE_ITEM_DROP (\d+),([-.0-9]+),([-.0-9]+),([-.0-9]+)")


def verify(host, actor, player, row):
    item = row["item"]
    host.commands((
        f"/tp {player} {' '.join(map(str, ORIGIN))} 0 0",
        f"/gamemode survival {player}",
        f"/setblock {SUPPLY} minecraft:barrel",
        f'/data merge block {SUPPLY} {{Items:[{{Slot:0b,id:"{item}",count:1,'
        'components:{"create:package_address":"Drop Fixture"}}]}',
        f"/item replace entity {player} hotbar.0 from block {SUPPLY} container.0",
    ))
    actor.call("key", "1", "tap")
    multiplayer.until("the actual addressed Package to enter the active hand", lambda:
                      (actor.call("inventory")["held"] or {}).get("item") == item)
    clock = host.clock()
    actor.call("key", "q", "tap")
    multiplayer.until("the live Package to enter the world", lambda:
                      len(host.call("entities", 8, toss.ENTITY)["entities"]) == 1)
    multiplayer.until("the held item to be consumed", lambda: not actor.call("inventory")["held"])
    assert host.clock() == clock, "Package physics advanced before inspecting the drop."
    for peer in (host,) if actor is host else (host, actor):
        multiplayer.until("the Package conversion to reach the client", lambda:
                          len(peer.call("entities", 8, toss.ENTITY)["entities"]) == 1)
        assert not peer.call("entities", 8, "minecraft:item")["entities"]

    captures = DROP.findall((host.socket.parent / "ctl.log").read_text())
    assert len(captures) == 1, captures
    package_id, *raw = captures[0]
    assert host.call("entities", 8, toss.ENTITY)["entities"][0]["id"] == int(package_id)
    # The Java probe supplies known ItemEntity motion before the event. The
    # actual Q gesture has the regular per-drop random velocity.
    declared = (0.125, 0.2, -0.05)
    factors = tuple(float(row["d" + axis]) / value for axis, value in zip("xyz", declared, strict=True))
    wanted_motion = tuple(scale * float(value) for scale, value in zip(factors, raw, strict=True))
    toss.close(toss.package_vector(host, "Motion"), wanted_motion, "Package Q-drop motion", tolerance=1e-10)
    toss.close(toss.package_vector(host, "Pos"), POSITION, "Package Q-drop launch position")
    stack = toss.package_field(host, "equipment.mainhand")
    if item not in stack or "Drop Fixture" not in stack:
        raise RuntimeError(f"Package drop did not preserve the original payload: {stack}")
    print(f"The real Q drop preserved {item}, the address, and the Java velocity rule.")


def verify_chute(host, actor, player, row):
    host.command(f"/tp {player} 12.5 103 20.5")
    host.commands((
        "/setblock 13 104 20 minecraft:dropper[facing=east]",
        "/setblock 14 104 20 create:chute",
        '/data merge block 13 104 20 {Items:[{Slot:0b,id:"create:cardboard_package_12x12",count:1,'
        'components:{"create:package_address":"Drop Fixture 2"}}]}',
        "/setblock 12 104 20 minecraft:redstone_block",
    ))
    clock = host.clock()
    trace = host.socket.parent / "ctl.log"
    captures = []
    for tick in range(1, 12):
        host.step_to(clock + tick)
        captures = CHUTE_SPAWN.findall(trace.read_text())
        if captures:
            break
    if len(captures) != 1:
        raise RuntimeError("The powered dropper did not spawn one world Package in the Chute.")
    package_id, *coords = captures[0]
    toss.close(tuple(map(float, coords)), (14.5, 103.75, 20.5), "Dropper Package spawn position")
    for peer in (host,) if actor is host else (host, actor):
        multiplayer.until("the Chute Package to reach the observer",
                          lambda: [entry["id"] for entry in peer.call("entities", 8, toss.ENTITY)["entities"]]
                          == [int(package_id)])
        assert not peer.call("entities", 8, "minecraft:item")["entities"]
    rotation = toss.package_field(host, "Rotation")
    angle = re.search(r"\[([-.0-9]+)f,", rotation)
    if row["snapped"] != "true" or not angle or float(angle[1]) % 90 != 0:
        raise RuntimeError(f"The Package did not adopt Java's ninety-degree Chute yaw: {rotation}")
    assert toss.package_field(host, "equipment.mainhand").find("Drop Fixture 2") >= 0
    assert host.command("/data get block 13 104 20 Items").endswith("[]")
    print("The dropper created a tracked Package with the original Chute yaw and full address.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    style = parser.add_mutually_exclusive_group()
    style.add_argument("--rare", action="store_true")
    style.add_argument("--chute", action="store_true")
    args = parser.parse_args()
    os.environ["HORIZON_CREATE_PACKAGE_TRACE"] = "1"
    with (ROOT / "fixtures/package-drop-java.csv").open() as source:
        row = list(csv.DictReader(source))[2 if args.chute else int(args.rare)]
    with fixture_world(args, "PackageDropLAN" if args.lan else "PackageDrop", render=True, pack=args.pack) as host:
        host.command("/fill 9 102 17 17 102 24 minecraft:stone")
        replay = verify_chute if args.chute else verify
        if args.lan:
            host.command("/tp @s 10.5 103 20.5")
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with TemporaryDirectory(prefix="hcd-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True, scenario="package-drop", pack=args.pack,
            ) as guest:
                multiplayer.until("the LAN guest to join", lambda: any(
                    item["name"] == GUEST and item["placed"] for item in host.call("lan", "status")["guests"]
                ))
                return replay(host, guest, GUEST, row)
        replay(host, host, "@s", row)


if __name__ == "__main__":
    main()
