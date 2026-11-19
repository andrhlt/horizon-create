#!/usr/bin/env python3
"""Replay the original Item Drain with honey, a water bucket, and a solid stack."""
import argparse
import csv
from math import isclose
from pathlib import Path
import re
import time

from fixture_world import ROOT, fixture_world

START = (
    ("minecraft:honey_bottle", 1),
    ("minecraft:water_bucket", 1),
    ("minecraft:iron_ingot", 3),
)


def values(tag):
    def read(pattern, default):
        match = re.search(pattern, tag)
        return match[1] if match else default

    item = re.search(r'HeldItem: \{.*?Item: \{([^}]+)\}', tag)
    contents = item[1] if item else ""
    item_id = re.search(r'id: "([^"]+)"', contents)
    count = re.search(r'count: (\d+)', contents)
    return (
        int(read(r'\bProcessingTicks: (\d+)', 0)),
        item_id[1] if item_id else "minecraft:air",
        int(count[1]) if count else 0,
        float(read(r'\bPos: ([-.\d]+)f', 0)),
        read(r'(?s)\bTankContent: \{Fluid: \{[^}]*id: "([^"]+)"', "minecraft:empty"),
        int(read(r'\bTankContent: \{Fluid: \{[^}]*amount: (\d+)', 0)),
    )


def run(args):
    with (ROOT / "fixtures/item-drain-java.csv").open() as stream:
        expected = list(csv.DictReader(stream))
    positions = [f"8 180 {23 + 2 * index}" for index in range(len(START))]
    frames = expected_frames() if args.fluid_visual else {}
    env = {"CREATE_ITEM_DRAIN_VISUAL": "1"} if frames else None
    with fixture_world(args, "Item-drain", render=args.visual or args.fluid_visual, env=env) as control:
        control.command("/setblock 7 180 24 minecraft:barrier")
        control.command("/tp @s 7.5 181 24.5")
        for index, (item, count) in enumerate(START):
            z = 23 + index * 2
            control.commands((
                f"/setblock 9 180 {z} minecraft:smooth_stone",
                f"/setblock {positions[index]} create:item_drain",
                f"/item replace block {positions[index]} container.0 with {item} {count}",
                f"/data merge block {positions[index]} {{HeldItem:{{Pos:0.0f,InDirection:5}}}}",
            ))
        if args.fluid_visual:
            control.call("look-at", 8.5, 180.85, 23.5)
        start = control.clock()
        with (ROOT / ".local/item-drain-horizon.csv").open("w", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(expected[0])
            for row in expected:
                tick, rig = int(row["tick"]), int(row["rig"])
                if rig == 0:
                    control.step_to(start + tick)
                tag = control.command(f"/data get block {positions[rig]}")
                actual = values(tag)
                reference = (
                    int(row["processing"]), row["item"], int(row["count"]),
                    float(row["position"]), row["fluid"], int(row["amount"]),
                )
                writer.writerow((tick, rig, *actual))
                if actual != reference:
                    raise RuntimeError(f"Tick {tick} rig {rig}: Java {reference}, Horizon {actual}. NBT {tag}")
                if frames and rig == 0:
                    wait_for_frames(control, start + tick, frames[tick])
                if (args.visual or args.fluid_visual) and (tick, rig) == (12, 0):
                    control.call("look-at", 8.5, 180.95, 23.5)
                    control.call("screenshot", ROOT / ".local/item-drain-honey.png")

        # A hopper feeds one bottle from the west without a synthetic held item tag.
        control.commands((
            "/setblock 9 180 29 minecraft:smooth_stone",
            "/setblock 8 180 29 create:item_drain",
            "/setblock 7 180 29 minecraft:hopper[facing=east]",
            "/item replace block 7 180 29 container.0 with minecraft:honey_bottle 3",
        ))
        control.step_to(start + 36)
        hopper = control.command("/data get block 7 180 29")
        drain = control.command("/data get block 8 180 29")
        if "count: 2" not in hopper or "InDirection: 5" not in drain or values(drain)[1:3] != ("minecraft:honey_bottle", 1):
            raise RuntimeError(f"Side insertion did not carry one bottle east: {hopper} / {drain}")
    print(f"Item Drain matched all {len(expected)} original Java transport, item and fluid samples.")
    print("A west hopper fed one bottle east and retained the other two.")
    if frames:
        print(f"Item Drain matched all {sum(map(len, frames.values()))} Java liquid levels, heights and stream radii.")
    if args.plumbing:
        test_plumbing(args)


def expected_frames():
    from collections import defaultdict

    frames = defaultdict(dict)
    with (ROOT / "fixtures/item-drain-fluid-visual-java.csv").open() as stream:
        for row in csv.DictReader(stream):
            frames[int(row["tick"])][float(row["partial"])] = tuple(
                float(row[name]) for name in ("level", "height", "radius")
            )
    return frames


def wait_for_frames(control, tick, expected):
    log = control.socket.parent / "ctl.log"
    prefix = f"CREATE_DRAIN_FRAME {tick} 8 180 23 "
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        found = {}
        completed, _, _ = log.read_text(encoding="utf-8").rpartition("\n")
        for row in completed.splitlines():
            if row.startswith(prefix):
                partial, *numbers = map(float, row.removeprefix(prefix).split())
                found[partial] = numbers
        if all(phase in found and all(
            isclose(actual, ref, abs_tol=1e-7)
            for actual, ref in zip(found[phase], values, strict=True)
        ) for phase, values in expected.items()):
            return
        control.call("wait", 2)
    raise RuntimeError(f"Frame for world tick {tick}: Java {expected}, Horizon {found}")


def test_plumbing(args):
    with fixture_world(args, "Drain-plumbing", render=True) as control:
        control.commands((
            "/fill 3 96 -12 9 96 -6 minecraft:smooth_stone",
            "/setblock 4 97 -9 create:item_drain",
            "/tp @s 4.5 97 -6.5 180 30",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with minecraft:honey_bottle 3",
        ))
        control.call("select", "minecraft:honey_bottle")
        control.call("wait", 3)
        control.call("interact", 4, 97, -9, "up")
        inventory = control.call("inventory")["counts"]
        source = control.command("/data get block 4 97 -9")
        if inventory.get("minecraft:honey_bottle") != 2 or inventory.get("minecraft:glass_bottle") != 1:
            raise RuntimeError(f"Pouring a held bottle left the wrong inventory: {inventory}")
        if values(source)[-2:] != ("create:honey", 250):
            raise RuntimeError(f"The bottle did not fill the drain with honey: {source}")
        control.commands((
            "/setblock 5 97 -9 create:mechanical_pump[facing=east,waterlogged=false]",
            "/setblock 6 97 -9 create:fluid_tank",
            "/setblock 4 98 -9 create:creative_motor[facing=east]{ScrollValue:64}",
            "/setblock 5 98 -9 create:cogwheel[axis=x]",
        ))
        start = control.clock()
        for tick in range(1, 31):
            control.step_to(start + tick)
        source, tank = control.commands(("/data get block 4 97 -9", "/data get block 6 97 -9"))
        drained = values(source)[-2:] == ("minecraft:empty", 0)
        transferred = 'id: "create:honey"' in tank and re.search(r"amount: 250\b", tank)
        if not drained or not transferred:
            raise RuntimeError(f"Honey did not transfer from the drain to the tank: {source}; {tank}")
    print("A survival player poured one bottle of honey and a pump moved all 250 mB into a tank.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--fluid-visual", action="store_true")
    parser.add_argument("--plumbing", action="store_true")
    run(parser.parse_args())
