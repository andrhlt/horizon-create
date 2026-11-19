#!/usr/bin/env python3
"""Compare the original Stockpile Switch filter item transforms and visible geometry."""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from math import isclose
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from fixture_world import ROOT, fixture_world


ENV = "CREATE_STOCKPILE_FILTER_RENDER"
TRACE = "CREATE_STOCKPILE_FILTER_FRAME "
TARGETS = ("down", "up", "north", "south", "west", "east")
SAMPLES = ("minecraft:stone", "minecraft:water_bucket")
GUEST = "StockpileView"
spec = spec_from_file_location("filter_input", ROOT / "tools/test-stockpile-switch-filter.py")
filters = module_from_spec(spec)
spec.loader.exec_module(filters)
editor = filters.editor


def reference():
    path = ROOT / "fixtures/stockpile-switch-filter-transform-java.csv"
    with path.open(newline="") as source:
        result = {(mount, face): tuple(map(float, raw)) for mount, face, *raw in csv.reader(source)}
    assert len(result) == 18
    return result


def render_frames(peer, expected, offset=0):
    log = peer.socket.parent / "ctl.log"
    until = monotonic() + 8
    seen = set()
    while monotonic() < until:
        for line in log.read_bytes()[offset:].decode(errors="replace").splitlines():
            if not line.startswith(TRACE):
                continue
            values = line[len(TRACE):].split(",")
            if len(values) != 16:
                continue
            x, y, z, mount, face, *raw, item, vertices = values
            key = ((int(x), int(y), int(z)), mount, face, item)
            if key not in expected or int(vertices) <= 0:
                continue
            read = tuple(map(float, raw))
            wanted = expected[key]
            assert len(wanted) == len(read) and all(
                isclose(a, b, abs_tol=.00002) for a, b in zip(wanted, read, strict=True)
            ), (key, wanted, read)
            seen.add(key)
        if seen == expected.keys():
            return
        sleep(.06)
    raise RuntimeError(f"Missing Stockpile render submissions {expected.keys() - seen}.")


def select_expected(mounts, item):
    expected = {}
    for pos, mount in mounts:
        for (target, face), pose in reference().items():
            if target != mount:
                continue
            body = (1.0 + 1 / 64, 0.0) if item == "minecraft:stone" else (.5 + 1 / 64, -.15)
            expected[pos, mount, face, item] = (*pose, *body)
    return expected


def shape(mount):
    attachment = {"down": "floor", "up": "ceiling"}.get(mount, "wall")
    facing = "south" if attachment != "wall" else mount
    return filters.wrench.state(facing, attachment)


def verify(args):
    mounts = [((8 + 3 * index, 102, -9), target) for index, target in enumerate(TARGETS)]
    with fixture_world(args, "StockpileFilterRender", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 6 100 -13 25 100 -1 minecraft:smooth_stone",
            "/fill 6 101 -13 25 106 -1 minecraft:air",
            "/tp @s 15.5 101 -2.5",
            *(f"/setblock {editor.xyz(pos)} {shape(mount)}" for pos, mount in mounts),
        ))
        for item in SAMPLES:
            log = control.socket.parent / "ctl.log"
            offset = log.stat().st_size
            control.commands(f'/data merge block {editor.xyz(pos)} {{Filter:{{id:"{item}",count:1}}}}' for pos, _ in mounts)
            for pos, _ in mounts:
                x, y, z = (coordinate + .5 for coordinate in pos)
                control.command(f"/tp @s {x} {y - 1.5} {z + 4}")
                control.call("look-at", x, y, z)
                control.call("wait", 4)
            render_frames(control, select_expected(mounts, item), offset)
    print("Both flat and block item meshes used all 18 original Stockpile Switch filter poses.")


def verify_lan(args, scratch):
    multiplayer = editor.load_multiplayer()
    pos = filters.POS[0]
    with fixture_world(args, "StockpileFilterRenderLAN", render=True, pack=args.pack) as host:
        filters.setup(host)
        host.command("/tp @s 11.5 101 -11.0")
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(
            args, scratch, address, GUEST, render=True, scenario="stockpile-filter-render", pack=args.pack,
        ) as guest:
            multiplayer.until("the filter-view guest to join", lambda: any(
                player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            host.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} 8.5 101 -11.5"))
            editor.wait_for(guest, "the filter-view guest to approach", lambda:
                guest.call("state")["player"]["position"][:3] == [8.5, 101., -11.5]
            )
            filters.equip(host, guest, GUEST, "minecraft:stone", 3)
            host.call("look-at", 8.5, 102.5, -8.5)
            filters.aim(guest, pos, "north", True)
            peers = (host, guest)
            offsets = [(p.socket.parent / "ctl.log").stat().st_size for p in peers]
            guest.call("mouse", "right", "click")
            editor.wait_for(host, "the guest's filter choice", lambda:
                filters.filter_data(filters.read(host, pos)) == ("minecraft:stone", 3)
            )
            expected = select_expected([(pos, "south")], "minecraft:stone")
            for peer, start in zip(peers, offsets, strict=True):
                render_frames(peer, expected, start)
    print("Both players rendered the guest’s selected stone filter on the three original active faces.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    os.environ[ENV] = "1"
    if args.lan:
        with TemporaryDirectory(prefix="hc-stfr-") as scratch:
            verify_lan(args, Path(scratch))
    else:
        verify(args)


if __name__ == "__main__":
    main()
