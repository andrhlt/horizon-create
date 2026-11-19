#!/usr/bin/env python3
"""Compare the original configured List Filter across detector target types."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
import re

from fixture_world import ROOT, fixture_world


observer = import_module("test-smart-observer-filter")
filters = observer.filters
editor = filters.editor
POSITIONS = [(8 + 5 * lane, 102, -9) for lane in range(5)]
MODE = "create:filter_items_blacklist"
ITEMS = "create:filter_items"
FILTER = "create:filter"
SAMPLES = '{slot:0,item:{id:"minecraft:stone",count:1}},{slot:1,item:{id:"minecraft:water_bucket",count:1}}'


def setup(host):
    host.commands((
        "/fill 4 100 -14 30 100 -5 minecraft:smooth_stone",
        "/fill 4 101 -14 30 108 -5 minecraft:air",
        "/setblock 8 102 -8 minecraft:stone",
        "/setblock 13 102 -8 minecraft:barrel",
        "/item replace block 13 102 -8 container.0 with minecraft:stone 16",
    ))
    for lane, pos in enumerate(POSITIONS):
        if lane >= 2:
            target = (pos[0], pos[1], pos[2] + 1)
            fluid = "minecraft:lava" if lane == 3 else "minecraft:water"
            host.commands((
                f"/setblock {editor.xyz(target)} create:fluid_tank",
                f'/data merge block {editor.xyz(target)} {{TankContent:{{Fluid:{{id:"{fluid}",amount:2000}}}}}}',
            ))
        host.command(f"/setblock {pos[0] + 1} 101 -12 minecraft:barrel")
        state = filters.wrench.state("south", "wall") if lane == 4 else observer.state("south", "wall")
        host.command(f"/setblock {editor.xyz(pos)} {state}")
        if lane == 4:
            host.command(f"/data merge block {editor.xyz(pos)} {{OffBelowAmount:500.0f,OnAboveAmount:1500.0f}}")


def mode(host, pos):
    raw = host.command(f"/data get block {editor.xyz(pos)} Filter")
    if f'id: "{FILTER}"' not in raw:
        return 0
    assert all(f'id: "{sample}"' in raw for sample in ("minecraft:stone", "minecraft:water_bucket")), raw
    return 2 if re.search(fr'"{MODE}": (?:1b|true)\b', raw) else 1


def click(host, actor, name, pos, selection):
    feet = (pos[0] + .5, 101, pos[2] - 2.5)
    host.commands((f"/tp {name} {editor.xyz(feet)}", f"/clear {name}"))
    editor.wait_for(actor, "the actor to approach the detector", lambda:
        tuple(actor.call("state")["player"]["position"][:3]) == feet
    )
    if selection:
        black = str(selection == 2).lower()
        components = f'{{"{ITEMS}":[{SAMPLES}],"{MODE}":{black}}}'
        stack = f'{{Slot:0b,id:"{FILTER}",count:2,components:{components}}}'
        supply = (pos[0] + 1, 101, -12)
        host.command(f"/data merge block {editor.xyz(supply)} {{Items:[{stack}]}}")
        actor.call("interact", *supply, "west")
        editor.wait_for(actor, "the configured List Filter in the barrel", lambda: any(
            slot["slot"] == 300 and slot.get("stack") and slot["stack"]["item"] == FILTER
            for slot in actor.call("menu").get("slots", [])
        ))
        actor.call("click-slot", 300)
        actor.call("click-slot", 0)
        actor.call("close")
        editor.wait_for(actor, "the configured List Filter in hand", lambda:
            actor.call("inventory")["counts"].get(FILTER) == 2
        )
        actor.call("select", FILTER)
    else:
        editor.wait_for(actor, "the empty hand", lambda: not actor.call("inventory")["counts"])
    filters.aim(actor, pos, "north", True)
    actor.call("mouse", "right", "click")
    editor.wait_for(host, "the original List Filter selection to update", lambda: mode(host, pos) == selection)


def verify(args, scratch):
    with (ROOT / "fixtures/detector-list-filter-java.csv").open(newline="") as file:
        rows = list(csv.reader(file))
    assert len(rows) == 145
    with fixture_world(args, "DetectorListFilter", render=True, pack=args.pack) as host:
        setup(host)
        with filters.actor_for(host, args, scratch) as (actor, name):
            host.command(f"/gamemode survival {name}")
            start = host.clock()
            for tick in range(1, 29):
                host.step_to(start + tick)
                if tick in (4, 12, 22):
                    for pos in POSITIONS:
                        click(host, actor, name, pos, {4: 1, 12: 2, 22: 0}[tick])
                    assert host.clock() == start + tick
                if tick < 4:
                    continue
                for lane, pos in enumerate(POSITIONS):
                    recorded, target, selected, counter, raw, powered = rows[tick * 5 + lane]
                    assert (int(recorded), int(target)) == (tick, lane)
                    data = filters.read(host, pos)
                    assert mode(host, pos) == int(selected), (tick, lane, data)
                    if lane == 4:
                        actual = (editor.field(data, "CurrentAmount"), bool(editor.field(data, "Powered")),
                                  bool(editor.field(data, "PoweredAfterDelay")))
                        expected = (int(counter), raw == "true", powered == "true")
                        assert actual == expected, (tick, lane, expected, actual, data)
                    else:
                        assert editor.field(data, "TurnOff", 0) == int(counter), (tick, lane, counter, data)
                        query = f"/execute if block {editor.xyz(pos)} {observer.state('south', 'wall', powered)}"
                        assert host.command(query).startswith("Test passed"), (tick, lane, powered, data)
    who = "Guest" if scratch else "Host"
    print(f"{who} matched 125 Java stock and pulse readings after whitelist, blacklist and clear clicks on five targets.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-dlf-") as scratch:
            verify(args, Path(scratch))
    else:
        verify(args, None)


if __name__ == "__main__":
    main()
