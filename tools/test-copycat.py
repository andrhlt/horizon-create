#!/usr/bin/env python3
"""Replay Copycat material and Wrench uses from Java in Horizon survival."""

import argparse
import csv
from importlib import import_module
from itertools import groupby
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

wait_for = import_module("test-stone-palettes").wait_for

POS = (8, 170, 23)
SNBT_NAME = re.compile(r'\bName: "([^"]+)"')
COUNT = re.compile(r"\bcount: (\d+)")
KEY = re.compile(r'(\w+): "([^"]+)"')
JAVA_STATE = re.compile(r'Block\{([^}]+)\}(?:\[(.+)\])?')

def state_from_java(text):
    key, props = JAVA_STATE.fullmatch(text).groups()
    return key, dict(pair.split("=", 1) for pair in props.split(",")) if props else {}

def expected_inventory(text):
    return {item: int(count) for item, count in (
        entry.split("=", 1) for entry in text.split("|") if entry
    )}

def material_tag(control, pos=POS):
    message = control.command(f"/data get block {pos[0]} {pos[1]} {pos[2]} Material")
    if (name := SNBT_NAME.search(message)) is None:
        return "create:copycat_base", {}
    return name[1], {key: val for key, val in KEY.findall(message) if key != "Name"}

def put(control, item, count=1):
    control.command(f"/item replace entity @s hotbar.0 with {item} {count}")
    wait_for(f"{count} {item} in the hotbar",
             lambda: control.call("inventory")["hotbar"][0],
             lambda slot: (slot["item"], slot.get("count")) == (item, count))
    control.call("select", item)

def click(control, y, sneak):
    if sneak:
        control.call("key", "shift", "down")
        control.call("wait", 3)
    try:
        control.call("look-at", 8.99, y, 23.75)
        control.call("mouse", "right", "click")
        control.call("wait", 3)
    finally:
        if sneak:
            control.call("key", "shift", "up")

def run(args):
    path = ROOT / "fixtures/copycat-material-java.csv"
    with path.open() as file:
        rows = list(csv.DictReader(file))
    differences = []
    with fixture_world(args, "CopycatMaterials", render=True, pack=args.pack) as control:
        control.commands((
            "/setblock 8 169 23 minecraft:stone",
            "/setblock 10 168 23 minecraft:stone",
            "/gamemode survival",
            "/tp @s 10.5 169 23.75",
        ))
        for (wrapper, item), section in groupby(rows, lambda row: (row["wrapper"], row["material_item"])):
            block, raw_props = state_from_java(wrapper)
            props = ",".join(f"{key}={value}" for key, value in raw_props.items())
            control.commands(("/setblock 8 170 23 air", f"/setblock 8 170 23 {block}[{props}]", "/clear @s"))
            put(control, item, 4)
            y = 170.095 if block.endswith("_panel") else 170.25
            for row in section:
                action = row["action"]
                if action == "different":
                    put(control, "minecraft:dirt", 3)
                elif action.endswith("wrench"):
                    put(control, "create:wrench")
                before = control.clock()
                click(control, y, action == "sneak-wrench")
                assert control.clock() == before, (block, item, action, "advanced a game tick")
                control.commands(("/setblock 9 170 23 air", "/setblock 8 171 23 air"))
                expected_block, props = state_from_java(row["state"])
                actual = control.call("block", *POS)["state"]
                label, space, actual_props = actual.partition("[")
                if space:
                    actual_props = dict(pair.split("=", 1) for pair in actual_props[:-1].split(","))
                else:
                    actual_props = {}
                assert label == expected_block and actual_props == props, (block, item, action, row["state"], actual)
                if row["appearance"] != "-":
                    expected = state_from_java(row["appearance"])
                    observed = material_tag(control)
                    if observed != expected:
                        differences.append((block, item, action, expected, observed))
                        print("Material difference:", differences[-1], flush=True)
                    nbt = control.command("/data get block 8 170 23 Item")
                    count = int(match[1]) if (match := COUNT.search(nbt)) else 0
                    assert count == int(row["applied_count"]), (block, item, action, row["applied_count"], nbt)
                if row["result"] == "SUCCESS":
                    expected = expected_inventory(row["inventory"])
                    observed = control.call("inventory")["counts"]
                    assert expected == observed, (block, item, action, expected, observed)
                print(block, item, action, "observed", flush=True)
    assert not differences, differences
    print(f"Matched material observations for all {len(rows)} Java uses.")

def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
