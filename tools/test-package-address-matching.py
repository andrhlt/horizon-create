#!/usr/bin/env python3
"""Compare Java Package Filter results through Horizon Smart Observer inventories."""
import argparse
import csv
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


observer = import_module("test-smart-observer-filter")
filters = observer.filters
editor = filters.editor
package_editor = import_module("test-package-filter-editor")
ITEM = "create:package_filter"
ADDRESS = "create:package_address"
PACKAGE = "create:cardboard_package_12x12"
RARE = "create:rare_creeper_package"
DETECTORS = ((8, 102, -9), (13, 102, -9), (18, 102, -9))


def text(hex_value):
    return None if hex_value == "-" else bytes.fromhex(hex_value).decode()


def stack(item, address=None, count=1, trimmed=False):
    fields = {"id": item, "count": count}
    if address is not None:
        fields["components"] = {ADDRESS: address}
    if trimmed:
        fields["components"].update({
            "!minecraft:enchantments": {},
            "!minecraft:attribute_modifiers": {},
        })
    return json.dumps(fields, ensure_ascii=False, separators=(",", ":"))


def list_filter(sample):
    return ('{id:"create:filter",count:1,components:{"create:filter_items":'
            '[{slot:0,item:' + sample + '}],"create:filter_items_respect_nbt":1b}}')


def apply_case(host, requested, candidate_address, candidate_kind):
    sample = stack(ITEM, requested)
    kind = {
        "filter": ITEM,
        "filterConfigured": ITEM,
        "filterTrimmed": ITEM,
        "package": PACKAGE,
        "rare": RARE,
        "stone": "minecraft:stone",
    }[candidate_kind]
    configured = candidate_kind in ("filterConfigured", "filterTrimmed")
    observed = stack(kind, candidate_address if candidate_address or configured else None,
                     trimmed=candidate_kind == "filterTrimmed")
    for lane, pos in enumerate(DETECTORS):
        xyz = editor.xyz(pos)
        target = editor.xyz((pos[0], pos[1], pos[2] + 1))
        sample_filter = list_filter(sample) if lane == 1 else sample
        host.commands((
            f"/setblock {xyz} minecraft:air",
            f"/setblock {target} minecraft:air",
            f"/setblock {target} {'create:fluid_tank' if lane == 2 else 'minecraft:barrel'}",
            f"/setblock {xyz} {observer.state('south', 'wall')}",
        ))
        outcome = host.command(f"/data merge block {xyz} {{Filter:{sample_filter}}}")
        assert outcome.startswith("Modified"), outcome
        if lane == 2:
            host.command(f'/data merge block {target} {{TankContent:{{Fluid:{{id:"minecraft:water",amount:2000}}}}}}')
        else:
            host.command(f"/data merge block {target} {{Items:[{{Slot:0b,{observed[1:] }]}}")
    start = host.clock()
    host.step_to(start + 1)
    host.step_to(start + 2)
    result = []
    for lane, pos in enumerate(DETECTORS):
        active = host.command(f"/execute if block {editor.xyz(pos)} {observer.state('south', 'wall', 'true')}")
        result.append(active.startswith("Test passed"))
    return result


def verify_registry(host, actor, name, forms):
    for item, max_stack, fits_inside in forms:
        assert max_stack == "1" and fits_inside == "false"
        host.commands((f"/clear {name}", f"/give {name} {item} 2"))
        editor.wait_for(actor, f"two separate {item} stacks", lambda:
            actor.call("inventory")["counts"].get(item) == 2
        )
        slots = actor.call("inventory")["hotbar"]
        assert len([slot for slot in slots if slot and slot.get("item") == item and slot.get("count") == 1]) == 2, slots


def exercise_ordinary_route(host, actor, name, scratch):
    pos = DETECTORS[0]
    xyz = editor.xyz(pos)
    target = editor.xyz((pos[0], pos[1], pos[2] + 1))
    feet = (pos[0] + .5, 101, pos[2] - 2.5)
    host.commands((
        f"/setblock {xyz} minecraft:air",
        f"/setblock {target} minecraft:air",
        f"/setblock {target} minecraft:barrel",
        f"/setblock {xyz} {observer.state('south', 'wall')}",
        f"/gamemode survival {name}",
        f"/tp {name} {editor.xyz(feet)} 0 -80",
        f"/clear {name}",
        f"/item replace entity {name} hotbar.0 with {ITEM}",
    ))
    editor.wait_for(actor, "a blank Package Filter in hand", lambda:
        actor.call("inventory")["counts"].get(ITEM) == 1
    )
    actor.call("select", ITEM)
    actor.call("options-set", "guiScale", "2")
    package_editor.select_editor(actor)
    panel = package_editor.scope(actor, scratch / "editor.png")
    package_editor.replace_text(actor, "Workshop*")
    actor.call("click-at", *package_editor.point(panel, (194, 63)))
    editor.wait_for(host, "the saved Workshop address", lambda:
        package_editor.saved(host, name) == "Workshop*"
    )
    filters.aim(actor, pos, "north", True)
    actor.call("mouse", "right", "click")
    editor.wait_for(host, "the player-configured filter on the world detector", lambda:
        '"Workshop*"' in host.command(f"/data get block {xyz} Filter")
    )
    item = stack(PACKAGE, "Workshop-4")
    host.command(f"/data merge block {target} {{Items:[{{Slot:0b,{item[1:] }]}}")
    host.step_to(host.clock() + 1)
    actual = host.command(f"/execute if block {xyz} {observer.state('south', 'wall', 'true')}")
    assert actual.startswith("Test passed"), actual


def measured(args, scratch):
    with (ROOT / "fixtures/package-address-java.csv").open(newline="") as file:
        rows = list(csv.reader(file))
    with (ROOT / "fixtures/package-items-java.csv").open(newline="") as file:
        forms = list(csv.reader(file))
    assert len(rows) == 40 and len(forms) == 14
    with fixture_world(args, "PackageAddressMatching", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 4 100 -14 24 100 -4 minecraft:smooth_stone",
            "/fill 4 101 -14 24 110 -4 minecraft:air",
            "/tp @s 8.5 101 -11.5 0 -80",
        ))
        with filters.actor_for(host, args, scratch if args.lan else None) as (actor, name):
            verify_registry(host, actor, name, forms)
            for index, requested, candidate, kind, *reference in rows:
                expected = [word == "true" for word in reference]
                actual = apply_case(host, text(requested), text(candidate), kind)
                assert actual == expected, (index, text(requested), text(candidate), kind, actual, expected)
            exercise_ordinary_route(host, actor, name, scratch)
    print(f"{'Guest' if args.lan else 'Host'} matched 40 Java address cases with 120 item/fluid readings, 14 unstackable package forms and a player-configured detector.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-packages-") as scratch:
        measured(args, Path(scratch))


if __name__ == "__main__":
    main()
