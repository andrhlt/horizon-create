#!/usr/bin/env python3
"""Replay Java filter decisions through Smart Chute transfers and cold reopen."""

import argparse
import csv
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

list_editor = import_module("test-list-filter-editor")
filters = list_editor.filters
parse = list_editor.package.parsing
mp = import_module("test-multiplayer")

FILTER = "create:filter"
ATTRIBUTE = "create:attribute_filter"
ADDRESS = "create:package_address"
PACKAGE = "create:cardboard_package_12x12"
STONE = "minecraft:stone"
PLANKS = "minecraft:oak_planks"
APPLE = "minecraft:apple"
POWER = "12 103 -3"
TICKS = 16


def stack(item, components=None):
    result = {"id": item, "count": 1}
    if components:
        result["components"] = components
    return result


def list_filter(*samples, deny=False):
    components = {list_editor.ENTRIES: [
        {"slot": slot, "item": item} for slot, item in enumerate(samples)
    ]}
    if deny:
        components[list_editor.BLACKLIST] = True
    return stack(FILTER, components)


def matrix():
    plain, stone, planks, apple = (stack(item) for item in (FILTER, STONE, PLANKS, APPLE))
    allow_stone = list_filter(stone)
    deny_stone = list_filter(stone, deny=True)
    nested, nested_blank = list_filter(deny_stone), list_filter(plain)
    attributes = {"create:attribute_filter_matched_attributes": [
        {"attribute": {"type": "create:in_tag", "value": "minecraft:planks"}, "inverted": False}
    ]}
    tag = stack(ATTRIBUTE, attributes)
    tag_deny = stack(ATTRIBUTE, attributes | {"create:attribute_filter_whitelist_mode": "blacklist"})
    package_filter = stack("create:package_filter", {ADDRESS: "Dock-*"})
    package_match = stack(PACKAGE, {ADDRESS: "Dock-East"})
    package_reject = stack(PACKAGE, {ADDRESS: "Other"})
    mixed = list_filter(tag, package_filter)
    return {
        "blank_match": (plain, plain), "blank_reject": (plain, stone),
        "allow_match": (allow_stone, stone), "allow_reject": (allow_stone, planks),
        "deny_match": (deny_stone, planks), "deny_reject": (deny_stone, stone),
        "nested_match": (nested, planks), "nested_reject": (nested, stone),
        "nested_blank_match": (nested_blank, plain), "nested_blank_reject": (nested_blank, stone),
        "tag_match": (tag, planks), "tag_reject": (tag, stone),
        "tag_deny_match": (tag_deny, stone), "tag_deny_reject": (tag_deny, planks),
        "package_match": (package_filter, package_match), "package_reject": (package_filter, package_reject),
        "mixed_tag": (mixed, planks), "mixed_package": (mixed, package_match),
        "mixed_reject": (mixed, apple), "cleared": ({}, apple),
    }


def xyz(position):
    return " ".join(map(str, position))


def blocks(position):
    x, y, z = position
    return xyz((x, y + 1, z)), xyz(position), xyz((x, y - 1, z))


def data(host, pos, field):
    raw = host.command(f"/data get block {pos} {field}")
    marker = "block data: "
    assert marker in raw, (pos, field, raw)
    return parse(raw.split(marker, 1)[1])


def fill_rig(host, position, installed, cargo):
    upper, chute, lower = blocks(position)
    host.commands((
        f"/setblock {upper} minecraft:barrel",
        f"/setblock {lower} minecraft:barrel",
        f"/setblock {chute} create:smart_chute",
        f"/data merge block {chute} {{Filter:{json.dumps(installed)}}}",
        f'/data merge block {upper} {{Items:[{json.dumps({"Slot": 0, **cargo})}]}}',
    ))
    assert cargo == contents(host, upper, lower)[0]


def contents(host, upper, lower):
    items = []
    for pos in (upper, lower):
        stacks = data(host, pos, "Items")
        assert len(stacks) <= 1, stacks
        items.append({key: value for key, value in stacks[0].items() if key != "Slot"} if stacks else {})
    return tuple(items)


def step(host, count):
    tick = host.clock()
    for offset in range(1, count + 1):
        host.step_to(tick + offset)


def compare(host, cases, reference):
    with reference.open(newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == len(cases) and {row["case"] for row in rows} == set(cases), rows
    rigs = {}
    for index, name in enumerate(cases):
        position = (4 + (index % 5) * 3, 103, -15 + (index // 5) * 3)
        fill_rig(host, position, *cases[name])
        rigs[name] = position
    step(host, TICKS)
    mismatches = []
    for row in rows:
        name = row["case"]
        upper, _, lower = blocks(rigs[name])
        actual = contents(host, upper, lower)
        cargo = cases[name][1]
        expected = tuple(cargo if row[side] == "1" else {} for side in ("source", "destination"))
        if actual != expected:
            mismatches.append((name, expected, actual))
    assert not mismatches, mismatches
    print(f"Matched all {len(rows)} Smart Chute snapshots from {reference.name} at tick {TICKS}.", flush=True)


def save_mixed_filter(host, actor, name, scratch, samples):
    feet = (8.5, 101, -9.5)
    host.commands((
        f"/gamemode survival {name}",
        f"/tp {name} {xyz(feet)} 0 -80",
        f"/item replace entity {name} hotbar.0 with {FILTER}",
        "/setblock 9 101 -10 minecraft:barrel",
        f'/data merge block 9 101 -10 {{Items:{json.dumps([{"Slot": i, **s} for i, s in enumerate(samples)])}}}',
    ))
    mp.until("the player to reach the supplies", lambda:
             actor.call("state")["player"]["position"] == list(feet))
    actor.call("interact", 9, 101, -10, "west")
    mp.until("the two samples to appear in the barrel menu", lambda:
             len([slot for slot in actor.call("menu").get("slots", [])
                  if slot["slot"] in (300, 301) and slot.get("stack")]) == 2)
    for slot in (0, 1):
        actor.call("click-slot", 300 + slot)
        actor.call("click-slot", 1 + slot)
    actor.call("close")
    mp.until("the configured samples in the hotbar", lambda:
             all(actor.call("inventory")["counts"].get(sample["id"]) == 1 for sample in samples))
    actor.call("select", FILTER)
    actor.call("options-set", "guiScale", "2")
    actor.call("look-at", 8.5, 110, -9.5)
    list_editor.open_editor(actor)
    panel = list_editor.scope(actor, scratch / "mixed-list-editor.png")
    list_editor.click(actor, panel, (63, 186), shift=True)
    list_editor.click(actor, panel, (82, 186), shift=True)
    list_editor.click(actor, panel, (190, 84))
    mp.until("the composed filter to save", lambda:
             len(list_editor.component_state(host, name).get(list_editor.ENTRIES, [])) == 2)
    assert actor.call("inventory")["counts"] == {item: 1 for item in (FILTER, *(s["id"] for s in samples))}
    raw = host.command(f"/data get entity {name} SelectedItem")
    return parse(raw.split("entity data: ", 1)[1])


def persistence(host, actor, name, scratch, cases):
    mixed, planks = cases["mixed_tag"]
    package = cases["mixed_package"][1]
    apple = cases["mixed_reject"][1]
    samples = [entry["item"] for entry in mixed["components"][list_editor.ENTRIES]]
    selected = save_mixed_filter(host, actor, name, scratch, samples)
    assert selected["components"][list_editor.ENTRIES] == mixed["components"][list_editor.ENTRIES], selected

    idle = (8, 103, -3)
    active = (11, 103, -3)
    fill_rig(host, idle, selected, apple)
    fill_rig(host, active, selected, package)
    active_upper, active_chute, active_lower = blocks(active)
    idle_upper, idle_chute, idle_lower = blocks(idle)
    step(host, 1)
    assert contents(host, active_upper, active_lower) == ({}, {})
    # Hold the captured in-flight stack while startup ticks run before the control socket freezes.
    host.command(f"/setblock {POWER} minecraft:redstone_block")
    step(host, 4)
    active_saved = data(host, active_chute, "Items")
    assert len(active_saved) == 1 and active_saved[0]["id"] == PACKAGE, active_saved
    assert contents(host, idle_upper, idle_lower) == (apple, {})
    assert data(host, idle_chute, "Filter") == data(host, active_chute, "Filter") == selected
    return active_saved, selected, idle, active, apple, package, planks


def reopen(host, before):
    active_saved, selected, idle, active, apple, package, planks = before
    active_upper, active_chute, active_lower = blocks(active)
    idle_upper, idle_chute, idle_lower = blocks(idle)
    host.restart()
    assert data(host, idle_chute, "Filter") == data(host, active_chute, "Filter") == selected
    assert data(host, active_chute, "Items") == active_saved
    assert contents(host, active_upper, active_lower) == ({}, {})
    assert contents(host, idle_upper, idle_lower) == (apple, {})
    host.command(f"/setblock {POWER} minecraft:air")
    step(host, TICKS)
    assert contents(host, active_upper, active_lower) == ({}, package)
    assert contents(host, idle_upper, idle_lower) == (apple, {})
    host.command(f'/data merge block {idle_upper} {{Items:[{json.dumps({"Slot": 0, **planks})}]}}')
    step(host, TICKS)
    assert contents(host, idle_upper, idle_lower) == ({}, planks)
    print("Cold reopen preserved both mounted filters, refused the idle control, and delivered the in-flight Package.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/item-filter-chute-java.csv")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    world = "ItemFilterChuteLAN" if args.lan else "ItemFilterChute"
    with TemporaryDirectory(prefix="hc-filter-") as scratch:
        with fixture_world(args, world, render=True, pack=args.pack) as host:
            host.commands((
                "/fill 2 100 -17 18 100 0 minecraft:smooth_stone",
                "/fill 2 101 -17 18 110 0 minecraft:air",
                "/tp @s 8.5 101 -9.5",
            ))
            cases = matrix()
            compare(host, cases, args.reference)
            with filters.actor_for(host, args, Path(scratch) if args.lan else None) as (actor, name):
                before = persistence(host, actor, name, Path(scratch), cases)
                print(f"{'Guest' if args.lan else 'Host'} composed the nested Attribute and Package samples in the List Filter editor.", flush=True)
            reopen(host, before)
            with filters.actor_for(host, args, Path(scratch) if args.lan else None) as (actor, name):
                mp.until("the reopened filter to reach the player's hotbar", lambda:
                         actor.call("inventory")["counts"].get(FILTER) == 1)
                actor.call("select", FILTER)
                mp.until("the editor's saved stack to be selected after reopening", lambda:
                         list_editor.component_state(host, name) == before[1]["components"])
                print("Cold reopen retained the player's edited List Filter and both nested samples.", flush=True)


if __name__ == "__main__":
    main()
