#!/usr/bin/env python3
"""Replay an Observer watching held Depot items and the independent processing buffer."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


observer = import_module("test-smart-observer-filter")
filters = observer.filters
editor = filters.editor
OBSERVERS = ((8, 102, -9), (13, 102, -9), (18, 102, -9))
DEPOTS = [(x, y, z + 1) for x, y, z in OBSERVERS]
ACTIONS = {4: "minecraft:stone", 11: None, 16: "minecraft:oak_planks", 20: None}


def counts(data):
    # DepotItem is the last client display stack, which clears on the next Depot tick.
    items = {}
    stored = re.search(r"\bItems: \[([^]]*)\]", data)
    for entry in re.findall(r"\{([^{}]*)\}", stored[1] if stored else ""):
        slot = editor.field(entry, "Slot")
        if slot is not None:
            items[slot] = editor.field(entry, "count", 0)
    return items.get(0, 0), sum(items.values())


def setup(host):
    host.commands((
        "/fill 5 100 -14 21 100 -4 minecraft:smooth_stone",
        "/fill 5 101 -14 21 109 -4 minecraft:air",
        "/setblock 8 102 -6 minecraft:smooth_stone",
    ))
    for detector, depot in zip(OBSERVERS, DEPOTS, strict=True):
        at = editor.xyz(detector)
        host.commands((
            f"/setblock {editor.xyz(depot)} create:depot",
            f"/setblock {at} {observer.state('south', 'wall')}",
            f'/data merge block {at} {{Filter:{{id:"minecraft:stone",count:1}}}}',
        ))
    host.command('/data merge block 13 102 -8 {Items:[{Slot:1b,id:"minecraft:stone",count:4}]}')


def depot_click(host, actor, name, item):
    feet = (8.5, 103, -5.5)
    host.commands((f"/tp {name} {editor.xyz(feet)}", f"/clear {name}"))
    editor.wait_for(actor, "the player to stand above the depot", lambda:
        tuple(actor.call("state")["player"]["position"][:3]) == feet
    )
    filters.equip(host, actor, name, item, 4 if item else 1)
    actor.call("look-at", 8.5, 102.313, -7.5)
    actor.call("wait", 3)
    hit = actor.call("looking-at")["block"]
    assert hit and hit["pos"] == list(DEPOTS[0]) and hit["face"] == "up", hit
    actor.call("mouse", "right", "click")
    expected = (4, 4) if item else (0, 0)
    try:
        editor.wait_for(host, "the player's depot interaction to reach the host", lambda:
            counts(filters.read(host, DEPOTS[0])) == expected
        )
    except RuntimeError as error:
        data = filters.read(host, DEPOTS[0])
        raise RuntimeError((item, expected, counts(data), data, actor.call("inventory")["counts"], hit)) from error


def verify(args, scratch):
    with (ROOT / "fixtures/observer-depot-java.csv").open(newline="") as file:
        rows = list(csv.reader(file))
    assert len(rows) == 78
    with fixture_world(args, "ObserverDepot", render=True, pack=args.pack) as host:
        setup(host)
        with filters.actor_for(host, args, scratch) as (actor, name):
            host.command(f"/gamemode survival {name}")
            start = host.clock()
            for tick in range(26):
                if tick:
                    host.step_to(start + tick)
                if tick in ACTIONS:
                    depot_click(host, actor, name, ACTIONS[tick])
                if tick == 5:
                    host.command('/data merge block 18 102 -8 {Items:[{Slot:0b,id:"minecraft:stone",count:4}],BeltPosition:0.0f}')
                if tick == 13:
                    host.command('/data merge block 18 102 -8 {Items:[]}')
                assert host.clock() == start + tick
                for lane, detector in enumerate(OBSERVERS):
                    row_tick, row_lane, holding, all_items, turn_off, powered = rows[tick * len(OBSERVERS) + lane]
                    assert (int(row_tick), int(row_lane)) == (tick, lane)
                    depot = filters.read(host, DEPOTS[lane])
                    assert counts(depot) == (int(holding), int(all_items)), (tick, lane, depot)
                    data = filters.read(host, detector)
                    assert editor.field(data, "TurnOff", 0) == int(turn_off), (tick, lane, turn_off, data)
                    check = f"/execute if block {editor.xyz(detector)} {observer.state('south', 'wall', powered)}"
                    assert host.command(check).startswith("Test passed"), (tick, lane, powered, data)
    who = "Guest" if scratch else "Host"
    print(f"{who} matched all 78 original Detector/Depot observations including real placement, removal and the output buffer.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-obdpt-") as scratch:
            verify(args, Path(scratch))
    else:
        verify(args, None)


if __name__ == "__main__":
    main()
