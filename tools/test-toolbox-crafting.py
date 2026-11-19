#!/usr/bin/env python3
"""Compare Toolbox registration and crafting with the pinned Java trace."""

import argparse
import csv
import json
import re
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

machine = import_module("test-machine-crafting")
crafting = machine.crafting
snbt = import_module("test-train-schedule-entry").snbt


def reference(name):
    with (ROOT / "fixtures" / f"toolbox-{name}-java.csv").open(newline="") as source:
        return list(csv.DictReader(source))


def test_default_blocks(control):
    for index, row in enumerate(reference("defaults")):
        x = 8 + index % 4
        z = 20 + index // 4
        control.command(f'/setblock {x} 170 {z} {row["block"]}')
        live = control.call("block", x, 170, z)
        assert live["block"] == row["block"], (row, live)
        assert "axis=" not in live["state"], (row, live)
        assert f'facing={row["facing"]}' in live["state"], (row, live)
        assert f'waterlogged={row["waterlogged"]}' in live["state"], (row, live)
    print("All 16 Toolbox block IDs and default states matched Java.", flush=True)


def test_crafting(control, same_color):
    for row in reference("craft-base"):
        machine.replay(control, row)
        print(f'{row["recipe"]} matched Java.', flush=True)
    for row in reference("craft-same-dye" if same_color else "craft-dye"):
        source = "brown" if row["color"] != "brown" else "white"
        if same_color:
            source = row["color"]
        machine.replay(control, {
            "recipe": row["recipe"],
            "width": "2",
            "slots": f'minecraft:{row["color"]}_dye,create:{source}_toolbox',
            "output": row["output"],
            "count": row["count"],
            "remainder": "",
        })
        print(f'{source} to {row["color"]} dye matched Java.', flush=True)
    control.command("/clear @s")
    control.commands((
        '/item replace entity @s hotbar.0 with create:brown_toolbox[minecraft:custom_name="Fixture Toolbox",minecraft:custom_data={ToolboxFixture:17}]',
        "/item replace entity @s hotbar.1 with minecraft:blue_dye",
    ))
    control.call("interact", 12, 170, 24, "up")
    crafting.distribute(control, 0, (100,))
    crafting.distribute(control, 1, (101,))
    crafting.craft(control, "create:blue_toolbox", 1)
    control.call("close")
    stack = next(
        entry for entry in control.call("inventory")["hotbar"]
        if entry.get("item") == "create:blue_toolbox"
    )
    components = snbt(stack["components"])
    assert components["minecraft:custom_name"] == "Fixture Toolbox", components
    assert components["minecraft:custom_data"] == {"ToolboxFixture": 17}, components
    print("Dyeing retained the name and custom-data components.", flush=True)


def fixture_pack(source, target, rows):
    with ZipFile(source) as original, ZipFile(target, "w") as updated:
        tags = {}
        for row in rows:
            for tag in row["added_tags"].split(";"):
                entry = f"data/c/tags/item/{tag}.json"
                if entry not in tags:
                    tags[entry] = json.loads(original.read(entry))
                tags[entry]["values"].append(row["dye"])
        for item in original.infolist():
            tag = tags.get(item.filename)
            data = json.dumps(tag).encode() if tag is not None else original.read(item)
            updated.writestr(item, data)


def test_tag_dye(control, rows):
    for row in rows:
        if row["output"]:
            machine.replay(control, {
                "recipe": row["recipe"],
                "width": "2",
                "slots": f'{row["dye"]},{row["input"]}',
                "output": row["output"],
                "count": row["count"],
                "remainder": "",
            })
        else:
            control.command("/clear @s")
            control.commands((
                f'/item replace entity @s hotbar.0 with {row["dye"]}',
                f'/item replace entity @s hotbar.1 with {row["input"]}',
            ))
            control.call("interact", 12, 170, 24, "up")
            crafting.distribute(control, 0, (100,))
            crafting.distribute(control, 1, (101,))
            result = next((entry["stack"] for entry in control.call("menu")["slots"] if entry["slot"] == 200), None)
            assert result is None, (row, result)
            control.call("close")
    print("Five custom dye cases matched Java, including black fallback and rejection of two Toolboxes.", flush=True)


def stack_components(stack):
    return snbt(re.sub(r"\[I;\s*([^]]*)\]", r"[\1]", stack.get("components") or "{}"))


def test_packaged_dye(control):
    control.command("/clear @s")
    control.command('/item replace entity @s hotbar.0 with create:black_toolbox[minecraft:custom_name="Fixture Toolbox"]')
    control.call("wait", 3)
    control.call("select", "create:black_toolbox")
    control.call("interact", 13, 169, 25, "up")
    control.command("/item replace block 13 170 25 container.0 with minecraft:cobblestone 16")
    control.step_to(control.clock() + 1)
    control.call("look-at", 13.5, 170.3, 25.5)
    control.call("wait", 3)
    control.call("mouse", "left", "click")
    control.call("wait", 3)
    initial = next(entry for entry in control.call("inventory")["hotbar"] if entry.get("item") == "create:black_toolbox")
    expected = stack_components(initial)
    assert set(expected) == {"minecraft:custom_name", "create:toolbox_uuid", "create:toolbox_inventory"}, expected
    control.command("/item replace entity @s hotbar.1 with minecraft:blue_dye")
    control.call("wait", 3)
    control.call("interact", 12, 170, 24, "up")
    crafting.distribute(control, initial["slot"], (100,))
    crafting.distribute(control, 1, (101,))
    crafting.craft(control, "create:blue_toolbox", 1)
    control.call("close")
    packed = next(entry for entry in control.call("inventory")["hotbar"] if entry.get("item") == "create:blue_toolbox")
    assert stack_components(packed) == expected, (packed, expected)
    print("Recoloring a carried Toolbox retained the item UUID, eight filters, inventory and name.", flush=True)


def test_pack(args, pack, tags):
    with fixture_world(args, "Toolbox-crafting", render=True, pack=pack, env={"HORIZON_NO_AUDIO": "1"}) as control:
        test_default_blocks(control)
        control.commands((
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))
        test_crafting(control, args.same_color)
        if tags:
            test_tag_dye(control, tags)
        if args.portable_data:
            test_packaged_dye(control)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--same-color", action="store_true")
    parser.add_argument("--tag-dye", action="store_true")
    parser.add_argument("--portable-data", action="store_true")
    args = parser.parse_args()
    if args.tag_dye:
        rows = reference("craft-tag-dye")
        with TemporaryDirectory(prefix="toolbox-crafting-") as tmp:
            pack = Path(tmp) / "toolbox-dyes.hmod"
            fixture_pack(args.pack, pack, rows)
            test_pack(args, pack, rows)
    else:
        test_pack(args, args.pack, ())


if __name__ == "__main__":
    main()
