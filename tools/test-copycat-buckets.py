#!/usr/bin/env python3
"""Compare actual bucket actions and stored Copycat material against the Java fixture."""

import argparse
import csv
from importlib import import_module
from itertools import groupby
from pathlib import Path

from fixture_world import ROOT, fixture_world

copycat = import_module("test-copycat")
POS = (8, 170, 23)
ADJACENT = (9, 170, 23)


def block_state(control, pos):
    label, bracket, props = control.call("block", *pos)["state"].partition("[")
    return label, dict(entry.split("=", 1) for entry in props[:-1].split(",")) if bracket else {}


def run(args):
    with (ROOT / "fixtures/copycat-buckets-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    with fixture_world(args, "CopycatBuckets", render=True, pack=args.pack) as control:
        control.commands((
            "/gamemode survival",
            "/setblock 10 168 23 minecraft:stone",
            "/setblock 8 169 23 minecraft:stone",
            "/tp @s 10.5 169 23.75 90 18",
        ))
        material = '{Material:{Name:"minecraft:oak_log",Properties:{axis:"y"}},Item:{id:"minecraft:oak_log",count:1}}'
        for wrapper, samples in groupby(rows, key=lambda row: row["wrapper"]):
            ident, props = copycat.state_from_java(wrapper)
            properties = ",".join(f"{key}={value}" for key, value in props.items())
            control.commands((
                "/setblock 9 170 23 minecraft:air",
                f"/setblock 8 170 23 {ident}[{properties}]",
                f"/data merge block 8 170 23 {material}",
                "/clear @s",
            ))
            y = 170.095 if ident.endswith("_panel") else 170.25
            for row in samples:
                tick = control.clock()
                copycat.put(control, row["input"])
                copycat.click(control, y, False)
                copycat.wait_for(f"{ident} {row['input']} result",
                                 lambda: control.call("inventory")["held"],
                                 lambda held: bool(held) and held["item"] == row["held"])
                assert control.clock() == tick, row
                wrapper_state = block_state(control, POS)
                neighbor_state = block_state(control, ADJACENT)
                stored = copycat.material_tag(control)
                item = control.command("/data get block 8 170 23 Item")
                print(ident, row["input"], wrapper_state, neighbor_state, stored, item, flush=True)
                assert wrapper_state == copycat.state_from_java(row["state"]), row
                assert neighbor_state == copycat.state_from_java(row["adjacent"]), row
                assert stored == copycat.state_from_java(row["material"]), row
                count = copycat.COUNT.search(item)
                assert count and count[1] == row["consumed"], (row, item)
    print(f"Matched all {len(rows)} Java bucket interactions, fluids, and retained materials on the action tick.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
