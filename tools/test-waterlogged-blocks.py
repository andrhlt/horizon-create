#!/usr/bin/env python3
"""Replay real Java dispenser timing against waterloggable Horizon machines."""

import argparse
import csv
import json
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

ITEM = re.compile(r'\bid: "([^"]+)"')
WET = re.compile(r'\bwaterlogged=(true|false)')


def coords(at):
    return " ".join(map(str, at))


def power_at(positions, level):
    return [f"/setblock {x-1} {y+1} {z} {level}" for x, y, z in positions]


def stock(positions, item):
    return [f'/data merge block {x-1} {y} {z} {{Items:[{{Slot:0b,id:"{item}",count:1}}]}}' for x, y, z in positions]


def setup_belts(control, names, positions):
    for name, (x, y, z) in zip(names, positions, strict=True):
        is_belt = name == "create:belt"
        y_belt = y if is_belt else y - 1
        control.commands((
            f"/setblock {x} {y_belt} {z+1} create:shaft[axis=x]",
            f"/setblock {x} {y_belt} {z-1} create:shaft[axis=x]",
            f"/setblock {x} {y_belt} {z} minecraft:air",
            "/give @s create:belt_connector",
        ))
        control.call("tp", x + 2.5, y, z + 0.5)
        control.call("select", "create:belt_connector")
        for _ in range(3):
            if "create:belt_connector" in control.command("/data get entity @s SelectedItem"):
                break
            control.call("wait", 1)
        else:
            raise RuntimeError("The server did not equip the connector")
        for _ in range(2):
            control.call("interact", x, y_belt, z+1)
            if "CreateBeltFirstShaft" in control.command("/data get entity @s SelectedItem"):
                break
        else:
            raise RuntimeError("The first shaft was never selected")
        for _ in range(5):
            control.step_to(control.clock() + 1)
        control.call("interact", x, y_belt, z-1)
        middle = control.call("block", x, y_belt, z)
        assert middle["block"] == "create:belt" and "part=middle" in middle["state"], middle
        if not is_belt:
            control.command(f"/setblock {x} {y} {z} {name}")


def setup(control, names, positions, case):
    control.commands((
        "/tp @s 17.5 172.0 35.5",
        "/fill 7 169 24 28 169 44 minecraft:stone",
    ))
    control.call("wait", 7)
    if case == "waterlogged-belts":
        setup_belts(control, names, positions)
    elif case == "waterlogged-supported":
        for name, (x, y, z) in zip(names, positions, strict=True):
            if name == "create:steam_engine":
                control.command(f"/setblock {x} {y-1} {z} create:fluid_tank")
            elif name == "create:powered_shaft":
                control.commands((
                    f"/setblock {x+3} {y} {z} create:fluid_tank",
                    f"/setblock {x+2} {y} {z} create:steam_engine[face=wall,facing=west]",
                ))
            else:
                control.command(f"/setblock {x} {y} {z+1} minecraft:stone")
            control.command(f"/setblock {x} {y} {z} {name}")
    else:
        control.commands([f"/setblock {coords(at)} {name}" for at, name in zip(positions, names, strict=True)])
    control.commands([f"/setblock {x-1} {y} {z} minecraft:dispenser[facing=east]"
                      for x, y, z in positions])
    control.commands(stock(positions, "minecraft:water_bucket"))


def sample(control, positions, names, tick):
    script = ""
    for x, y, z in positions:
        script += f"block {x} {y} {z}\n"
        script += f"command {json.dumps(f'/data get block {x-1} {y} {z} Items')}\n"
    replies = control.call("script", script=script)
    vals = []
    for name, block, dispenser in zip(names, replies[::2], replies[1::2], strict=True):
        wet = WET.search(block["state"])
        item = ITEM.search(dispenser["chat"][-1])
        vals.append((str(tick), name, block["block"], wet[1] if wet else "absent", item[1] if item else "minecraft:air"))
    return vals


def run(args):
    if args.belts:
        case, world, subject_count = "waterlogged-belts", "WaterloggedBelts", 3
    elif args.supported:
        case, world, subject_count = "waterlogged-supported", "WaterloggedSupported", 6
    else:
        case, world, subject_count = "waterlogged-blocks", "WaterloggedMachines", 26
    source = ROOT / "fixtures" / f"{case}-java.csv"
    with source.open() as trace:
        expected = list(csv.reader(trace))[1:]
    initial = [row for row in expected if row[0] == "0"]
    assert len(initial) == subject_count and len(expected) == 13 * subject_count
    names = [row[1] for row in initial]
    positions = [tuple(map(int, row[2:5])) for row in initial]
    expected = [row[:2] + row[5:] for row in expected]
    actual = []
    with fixture_world(args, world, pack=args.pack) as control:
        setup(control, names, positions, case)
        baseline = control.clock()
        for tick in range(13):
            if tick:
                control.step_to(baseline + tick)
            actual.extend(sample(control, positions, names, tick))
            if tick == 0:
                control.commands(power_at(positions, "minecraft:redstone_block"))
            elif tick == 6:
                control.commands(power_at(positions, "minecraft:air"))
                control.commands(stock(positions, "minecraft:bucket"))
                control.commands(power_at(positions, "minecraft:redstone_block"))
    diffs = [(want, got) for want, got in zip(expected, actual, strict=True) if tuple(want) != got]
    log = ROOT / ".local" / f"{case}-horizon.csv"
    with log.open("w", newline="") as out:
        csv.writer(out, lineterminator="\n").writerows(actual)
    if diffs:
        ids = sorted({want[1] for want, _ in diffs})
        for want, got in diffs[:40]:
            print(want, got, flush=True)
        raise RuntimeError(f"{len(diffs)} differing samples across {len(ids)} blocks: {ids}")
    print(f"All {len(actual)} Java dispenser samples across {len(names)} blocks matched tick for tick.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    fixture = parser.add_mutually_exclusive_group()
    fixture.add_argument("--supported", action="store_true", help="test blocks that require placement support")
    fixture.add_argument("--belts", action="store_true", help="test connected belts and their funnels")
    run(parser.parse_args())
