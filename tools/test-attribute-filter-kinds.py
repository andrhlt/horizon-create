#!/usr/bin/env python3
"""Compare Java Attribute Filter item types against Horizon Stockpile Switch sampling."""
import argparse
from ast import literal_eval
import csv
from importlib import import_module
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


filters = import_module("test-stockpile-switch-filter")
editor = filters.editor
ITEM = "create:attribute_filter"
MATCH = "create:attribute_filter_matched_attributes"
STATE = filters.wrench.state("south", "wall")
SWITCH = (8, 102, -9)
TARGET = (8, 102, -8)
SUPPLY = (9, 101, -12)


def original_string(value):
    return bytes.fromhex(value).decode()


def component_format(sample):
    key = "minecraft:custom_name"
    if key not in sample:
        return sample
    # Java 1.21.1 saves components as JSON strings. Horizon 26.3 stores the
    # same text as a native string or compound, including literal JSON text.
    quoted_text = r"""("minecraft:custom_name":\s*)("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')"""
    def native_string(match):
        component = json.loads(literal_eval(match[2]))
        return match[1] + json.dumps(component, ensure_ascii=False, separators=(",", ":"))
    converted, matched = re.subn(quoted_text, native_string, sample, count=1)
    assert matched == 1, sample
    return converted


def apply_case(host, attribute, sample):
    sample = component_format(sample)
    sensor, inventory = editor.xyz(SWITCH), editor.xyz(TARGET)
    filter_tag = f'{{id:"{ITEM}",count:1,components:{{"{MATCH}":[{{attribute:{attribute},inverted:0b}}]}}}}'
    host.commands((
        f"/setblock {sensor} minecraft:air",
        f"/setblock {inventory} minecraft:air",
        f"/setblock {inventory} minecraft:barrel",
        f"/setblock {sensor} {STATE}",
    ))
    for command in (
        f"/data merge block {inventory} {{Items:[{{Slot:0b,{sample[1:]}]}}",
        f"/data merge block {sensor} {{SampleDelay:0,Filter:{filter_tag}}}",
    ):
        result = host.command(command)
        assert result.startswith("Modified"), result
    host.step_to(host.clock() + 1)
    return editor.field(filters.read(host, SWITCH), "CurrentAmount")


def by_hand(host, actor, name, *,
            kind="create:renamed", value="{}",
            sample='{Slot:0b,id:"minecraft:stone",count:1,components:{"minecraft:custom_name":"Ore"}}'):
    sensor, inventory, supply = map(editor.xyz, (SWITCH, TARGET, SUPPLY))
    feet = (8.5, 101, -11.5)
    host.commands((
        f"/setblock {sensor} minecraft:air",
        f"/setblock {inventory} minecraft:air",
        f"/setblock {inventory} minecraft:barrel",
        f"/setblock {sensor} {STATE}",
        f"/setblock {supply} minecraft:barrel",
        f"/tp {name} {editor.xyz(feet)}",
        f"/gamemode survival {name}",
        f"/clear {name}",
    ))
    tag = f'{{attribute:{{type:"{kind}",value:{value}}},inverted:0b}}'
    value = f'{{Slot:0b,id:"{ITEM}",count:1,components:{{"{MATCH}":[{tag}]}}}}'
    host.command(f"/data merge block {supply} {{Items:[{value}]}}")
    actor.call("interact", *SUPPLY, "west")
    editor.wait_for(actor, "the configured filter stack in the supply barrel", lambda: any(
        slot["slot"] == 300 and slot.get("stack") and slot["stack"]["item"] == ITEM
        for slot in actor.call("menu").get("slots", [])
    ))
    actor.call("click-slot", 300)
    actor.call("click-slot", 0)
    actor.call("close")
    editor.wait_for(actor, "the configured Attribute Filter in hand", lambda:
        actor.call("inventory")["counts"].get(ITEM) == 1
    )
    actor.call("select", ITEM)
    filters.aim(actor, SWITCH, "north", True)
    actor.call("mouse", "right", "click")
    editor.wait_for(host, "the original configured filter on the switch", lambda:
        f'"{kind}"' in host.command(f"/data get block {sensor} Filter")
    )
    host.command(f"/data merge block {inventory} {{Items:[{sample}]}}")
    host.command(f"/data merge block {sensor} {{SampleDelay:0}}")
    host.step_to(host.clock() + 1)
    assert editor.field(filters.read(host, SWITCH), "CurrentAmount") == 1


def measured(args, temporary):
    with (ROOT / "fixtures/attribute-filter-kinds-java.csv").open(newline="") as file:
        rows = list(csv.reader(file))
    with (ROOT / "fixtures/attribute-filter-names-java.csv").open(newline="") as file:
        names = list(csv.reader(file))
    assert len(rows) == 53 and len(names) == 11
    with fixture_world(args, "AttributeFilterKinds", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 4 100 -14 16 100 -4 minecraft:smooth_stone",
            "/fill 4 101 -14 16 110 -4 minecraft:air",
            "/tp @s 8.5 101 -11.5 0 -80",
        ))
        with filters.actor_for(host, args, temporary if args.lan else None) as (actor, name):
            for index, kind, attribute, sample, expected in rows:
                nbt = original_string(sample)
                actual = apply_case(host, original_string(attribute), nbt)
                assert actual == int(expected == "true"), (index, kind, nbt, expected, actual)
            for input_name, selected in names:
                literal = original_string(input_name)
                expected = original_string(selected)
                source = json.dumps(
                    {"id": "minecraft:stone", "count": 1,
                     "components": {"minecraft:custom_name": json.dumps(literal, ensure_ascii=False)}},
                    ensure_ascii=False, separators=(",", ":"),
                )
                attribute = json.dumps({"type": "create:has_name", "value": expected}, ensure_ascii=False)
                assert apply_case(host, attribute, source) == 1, (literal, expected)
            by_hand(host, actor, name)
    print(f"{'Guest' if args.lan else 'Host'} matched 64 Java Attribute Filter readings across 12 item predicates and a real filter selection.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-afk-") as scratch:
        measured(args, Path(scratch))


if __name__ == "__main__":
    main()
