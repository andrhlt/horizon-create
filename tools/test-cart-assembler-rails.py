#!/usr/bin/env python3
"""Observe survival placement of an Assembler onto the four vanilla rail types."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world


def samples(args):
    with (ROOT / "fixtures/cart-assembler-placement-java.csv").open() as source:
        rows = csv.reader(source)
        next(rows)
        expected = list(rows)
    with fixture_world(args, "CartAssemblerPlacement", pack=args.pack) as control:
        control.commands((
            "/tp @s 17.5 172 26.5",
            "/fill 7 169 23 31 169 35 minecraft:stone",
            "/gamemode survival",
        ))
        control.call("wait", 5)
        failures = []
        for index, row in enumerate(expected):
            rail, shape, yaw, assembler, rail_type, backwards, placed_shape, wet, count = row
            x, y, z = 8 + (index // 2) * 6, 170, 24 + (index % 2) * 4
            control.commands((
                "/clear @s create:cart_assembler",
                f"/setblock {x} {y} {z} {rail}[shape={shape}]",
                "/give @s create:cart_assembler 2",
            ))
            px, pz = x + 2.5, z + 0.5
            control.call("tp", px, y + 1, pz)
            dz = 2 if yaw == "0" else -2
            control.call("look-at", px, y + 2.62, pz + dz)
            control.call("select", "create:cart_assembler")
            control.call("interact", x, y, z, "up")
            state = f"{assembler}[rail_type={rail_type},backwards={backwards},shape={placed_shape},waterlogged={wet}]"
            block, held = control.commands((
                f"/execute if block {x} {y} {z} {state}",
                "/data get entity @s SelectedItem",
            ))
            actual_count = re.search(r"\bcount: (\d+)", held)
            if ("Test passed" not in block
                    or f'id: "{assembler}"' not in held
                    or not actual_count or actual_count[1] != count):
                failures.append((row, control.call("block", x, y, z), held))
    if failures:
        raise RuntimeError(f"{len(failures)} Cart Assembler placements differed: {failures}")
    print(f"All {len(expected)} Java Cart Assembler placements matched.")


def dispenser(args):
    with (ROOT / "fixtures/cart-assembler-drain-java.csv").open() as source:
        rows = csv.reader(source)
        next(rows)
        expected = list(rows)
    with fixture_world(args, "CartAssemblerDrain", pack=args.pack) as control:
        control.commands((
            "/tp @s 10.5 171 32.5",
            "/fill 6 169 28 16 169 35 minecraft:stone",
            "/setblock 8 170 32 minecraft:rail",
            "/give @s create:cart_assembler",
        ))
        control.call("wait", 5)
        control.call("tp", 10.5, 171, 32.5)
        control.call("look-at", 8.5, 170.1, 32.5)
        control.call("select", "create:cart_assembler")
        control.call("interact", 8, 170, 32, "up")
        control.commands((
            "/setblock 7 170 32 minecraft:dispenser[facing=east]",
            '/data merge block 7 170 32 {Items:[{Slot:0b,id:"minecraft:water_bucket",count:1}]}',
        ))
        baseline = control.clock()
        actual = []
        for tick in range(13):
            if tick:
                control.step_to(baseline + tick)
            block, result = control.call(
                "script", script='block 8 170 32\ncommand "/data get block 7 170 32 Items"'
            )
            wet = re.search(r"\bwaterlogged=(true|false)", block["state"])
            item = re.search(r'\bid: "([^"]+)"', result["chat"][-1])
            drops = control.call("entities", 5, "minecraft:item")["entities"]
            items = sorted(entity["item"]["item"] for entity in drops)
            actual.append([str(tick), block["block"], wet[1] if wet else "absent",
                           item[1] if item else "minecraft:air", "|".join(items)])
            if tick == 0:
                control.command("/setblock 7 171 32 minecraft:redstone_block")
            elif tick == 6:
                control.commands((
                    "/setblock 7 171 32 minecraft:air",
                    '/data merge block 7 170 32 {Items:[{Slot:0b,id:"minecraft:bucket",count:1}]}',
                    "/setblock 7 171 32 minecraft:redstone_block",
                ))
    diffs = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    if diffs:
        for want, got in diffs:
            print(want, got)
        raise RuntimeError(f"{len(diffs)} Cart Assembler drain samples differed")
    print("All 13 Java Cart Assembler fill, drain, and drop samples matched tick for tick.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    samples(args)
    dispenser(args)
