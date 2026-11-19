#!/usr/bin/env python3
"""Compare player placement of a Smart Observer beside the original target types."""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


ITEM = "create:content_observer"
name = "ObserverMount"
spec = spec_from_file_location("stockpile_placement", ROOT / "tools/test-stockpile-switch-placement.py")
mounts = module_from_spec(spec)
spec.loader.exec_module(mounts)
editor = mounts.editor
POSITION = mounts.POSITION


def state(facing, mount, powered="false"):
    return f"{ITEM}[facing={facing},powered={powered},target={mount}]"


def verify(args):
    reference = ROOT / "fixtures/smart-observer-placement-java.csv"
    with reference.open(newline="") as source:
        rows = list(csv.reader(source))
    assert len(rows) == 15
    with fixture_world(args, "SmartObserverMount", render=True, pack=args.pack) as host:
        host.command("/gamemode survival")
        for case, block, face, yaw, pitch, sneaking, around, facing, mount, consumed in rows:
            support = mounts.offset(face, -1)
            mounts.setup(host, support, block, [] if around == "-" else around.split("+"))
            dx, dy, dz = mounts.DIRECTIONS[face]
            px, py, pz = POSITION
            feet = (px + .5 + 2 * dx + 2 * abs(dy), py - 1 + int(dy > 0) * 3, pz + .5 + 2 * dz)
            if dy > 0:
                host.command(f"/setblock {px + 2} {py + 1} {pz} minecraft:smooth_stone")
            host.commands((
                f"/tp @s {editor.xyz(feet)} {yaw} {pitch}",
                f"/item replace entity @s hotbar.0 with {ITEM}",
            ))
            host.call("wait", 3)
            host.call("select", ITEM)
            if sneaking == "true":
                host.call("key", "shift", "down")
                host.call("wait", 2)
            try:
                result = host.call("interact", *support, face)
            finally:
                if sneaking == "true":
                    host.call("key", "shift", "up")
            assert (result.get("inventory_change", {}).get(ITEM) == -1) == (consumed == "true"), (case, result)
            assert host.call("block", *POSITION)["state"] == state(facing, mount), (case, host.call("block", *POSITION))
    print("All 15 original Smart Observer placement cases matched, including the depot, pipe and funnel.")


def verify_lan(args, scratch):
    multiplayer = editor.load_multiplayer()
    support = mounts.offset("north", -1)
    with fixture_world(args, "SmartObserverMountLAN", render=True, pack=args.pack) as host:
        mounts.setup(host, support, "minecraft:barrel", ())
        host.commands((
            f"/item replace block {editor.xyz(support)} container.0 with minecraft:stone 32",
            "/tp @s 11.5 101 -8.5",
        ))
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(
            args, scratch, address, name, render=True, scenario="smart-observer-placement", pack=args.pack,
        ) as guest:
            multiplayer.until("the Smart Observer placer to join", lambda: any(
                player["name"] == name and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {name}",
                f"/tp {name} 8.5 101 -11.5",
                f"/item replace entity {name} hotbar.0 with {ITEM}",
            ))
            editor.wait_for(guest, "the guest to reach the barrel with the Smart Observer", lambda:
                guest.call("state")["player"]["position"][:3] == [8.5, 101., -11.5]
                and guest.call("inventory")["counts"].get(ITEM) == 1
            )
            guest.call("select", ITEM)
            guest.call("key", "shift", "down")
            try:
                guest.call("look-at", 8.5, 102.5, -8.001)
                guest.call("wait", 3)
                hit = guest.call("looking-at").get("block")
                assert hit and hit["pos"] == list(support) and hit["face"] == "north", hit
                guest.call("mouse", "right", "click")
                multiplayer.until("both players to see the observer face the barrel", lambda: all(
                    peer.call("block", *POSITION)["state"] == state("south", "wall") for peer in (host, guest)
                ))
            finally:
                guest.call("key", "shift", "up")
            host.step_to(host.clock() + 1)
            data = host.command(f"/data get block {editor.xyz(POSITION)}")
            assert editor.field(data, "TurnOff") == 6, data
            assert host.call("block", *POSITION)["state"] == state("south", "wall", "true")
            assert guest.call("inventory")["counts"].get(ITEM, 0) == 0
    print("A live guest mounted the observer, and the host detected the barrel's stock on the first tick.")


def verify_wrench(args):
    spec = spec_from_file_location("detector_filter", ROOT / "tools/test-smart-observer-filter.py")
    observer = module_from_spec(spec)
    spec.loader.exec_module(observer)
    filters = observer.filters
    with (ROOT / "fixtures/smart-observer-wrench-java.csv").open(newline="") as source:
        rows = list(csv.reader(source))
    assert len(rows) == 36
    with fixture_world(args, "SmartObserverWrench", render=True, pack=args.pack) as host:
        filters.wrench.arena(host)
        filters.wrench.equip(host, host, "@s")
        at = editor.xyz(POSITION)
        for observed, face, initial_power, facing, target, power, delay, count in rows:
            mount = {"up": "ceiling", "down": "floor"}.get(observed, "wall")
            horizontal = "south" if mount != "wall" else observed
            host.commands((
                f"/setblock {at} {state(horizontal, mount, initial_power)}",
                f'/data merge block {at} {{TurnOff:3,Filter:{{id:"minecraft:stone",count:3}}}}',
            ))
            filters.wrench.stand(host, host, "@s", face)
            tick = host.clock()
            host.call("interact", *POSITION, face)
            assert host.clock() == tick
            actual = host.call("block", *POSITION)["state"]
            assert actual == state(facing, target, power), (observed, face, actual)
            data = filters.read(host, POSITION)
            assert editor.field(data, "TurnOff") == int(delay), (observed, face, data)
            assert filters.filter_data(data) == ("minecraft:stone", int(count)), (observed, face, data)
    print("All 36 original Smart Observer Wrench rotations matched and preserved the sample and countdown.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--lan", action="store_true")
    modes.add_argument("--wrench", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-obm-") as scratch:
            verify_lan(args, Path(scratch))
    elif args.wrench:
        verify_wrench(args)
    else:
        verify(args)


if __name__ == "__main__":
    main()
