#!/usr/bin/env python3
"""Compare Create window defaults, pane joins, survival crafting and waterlogging."""

import argparse
import csv
import importlib.util
import json
from pathlib import Path
import re
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world
from prepare import crafting_ingredient, model_references
from stone_palettes import normalize_recipe, palette_recipes
from window_palettes import WINDOW_BLOCKS, WINDOW_IDS, window_face_culling

PANE = "create:oak_window_pane"
TARGET = (8, 97, -9)
TABLE = (5, 97, -11)


def load_helper(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


crafting = load_helper("test-survival-crafting")
stone = load_helper("test-stone-palettes")


def reference(name):
    with (ROOT / f"fixtures/window-{name}-java.csv").open() as source:
        return list(csv.DictReader(source))


def java_state(text):
    return re.sub(r"^Block\{([^}]+)\}", r"\1", text)


def check_state(control, expected):
    result = control.call("block", *TARGET)
    properties = stone.state_properties
    if result["block"] != expected.split("[", 1)[0] or properties(result["state"]) != properties(expected):
        raise RuntimeError(f"Java {expected}, Horizon {result['state']}")


def verify_pack(pack, java, rows):
    with ZipFile(pack) as archive:
        for row in rows:
            name = row["block"]
            block = json.loads(archive.read(f"data/create/horizon/block/{name}.json"))
            expected = {
                "map_color": int(row["map_color"]),
                "hardness": float(row["hardness"]),
                "explosion_resistance": float(row["resistance"]),
                "occludes": row["occludes"] == "true",
            }
            if mode := window_face_culling(name):
                expected["face_culling"] = mode
            if not block["item"] or block["properties"] != expected:
                raise RuntimeError(f"The {name} declaration differs from Java: {block}")
        if java is None:
            return
        roots = tuple(java / "src" / folder / "resources" for folder in ("main", "generated"))
        pending = [path for name in WINDOW_BLOCKS for path in (
            f"blockstates/{name}.json", f"models/item/{name}.json",
        )]
        saved = set()
        while pending:
            path = pending.pop()
            if path in saved:
                continue
            saved.add(path)
            relative = f"assets/create/{path}"
            data = next(root / relative for root in roots if (root / relative).is_file()).read_bytes()
            if archive.read(relative) != data:
                raise RuntimeError(f"Original bytes changed for {relative}")
            if relative.endswith(".json"):
                pending.extend(model_references(json.loads(data)))
        for name in WINDOW_BLOCKS:
            relative = f"data/create/loot_table/blocks/{name}.json"
            original = json.loads((roots[1] / relative).read_bytes())
            normalized = json.loads(archive.read(relative))
            pool, = normalized["pools"]
            condition = pool.pop("condition")
            condition["condition"] = condition.pop("type")
            pool["conditions"] = [condition]
            if normalized != original:
                raise RuntimeError(f"Original loot changed for {name}")
        recipes = list(palette_recipes(roots[1], WINDOW_IDS))
        for path, recipe in recipes:
            if json.loads(archive.read(str(path))) != normalize_recipe(recipe, crafting_ingredient):
                raise RuntimeError(f"Original window recipe changed: {path}")
        recycling = list((roots[1] / "data/create/recipe/smelting").glob("glass*_from_*glass*.json"))
        recycling = [path for path in recycling if f"create:{path.stem.split('_from_', 1)[1]}" in WINDOW_IDS]
        if len(recycling) != 8:
            raise RuntimeError(f"Expected eight glass recycling recipes, got {len(recycling)}")
        for path in recycling:
            relative = path.relative_to(roots[1]).as_posix()
            recipe = json.loads(path.read_bytes())
            recipe["ingredient"] = crafting_ingredient(recipe["ingredient"])
            if json.loads(archive.read(relative)) != recipe:
                raise RuntimeError(f"Original recycling recipe changed: {relative}")
        print(f"Matched {len(saved)} upstream assets, {len(rows)} loot tables and {len(recipes) + len(recycling)} recipes.")


def craft(control, item, count, ingredients):
    control.command("/clear @s")
    control.commands(f"/item replace entity @s hotbar.{i} with {source} {len(slots)}"
                     for i, (source, slots) in enumerate(ingredients))
    control.call("wait", 3)
    control.call("interact", *TABLE, "up")
    control.call("wait", 3)
    for i, (_, slots) in enumerate(ingredients):
        crafting.distribute(control, i, slots)
    crafting.craft(control, item, count)
    control.call("close")


def cut_glass(control, material, result, suffix):
    control.command("/clear @s")
    control.command(f"/item replace entity @s hotbar.0 with minecraft:{material}")
    control.call("wait", 2)
    control.call("interact", *TABLE, "up")
    control.call("wait", 2)
    control.call("click-slot", 0)
    stone.wait_for(material, lambda: control.call("menu").get("carried"),
                   lambda stack: bool(stack) and stack["item"] == f"minecraft:{material}")
    control.call("click-slot", 600)
    recipe = f"create:{result}_from_glass_{suffix}_colorless_stonecutting"
    options = stone.wait_for("four original glass patterns",
                             lambda: (control.call("menu").get("info") or {}).get("recipes", []),
                             lambda options: len(options) == 4 and recipe in options)
    index = options.index(recipe)
    nodes = control.call("ui")["widgets"]
    left, top, _, _ = next(node["bounds"] for node in nodes if node["id"] == "slot-600")
    control.call("click-at", left - 20 + 60 + index * 16, top - 33 + 23)
    control.call("click-slot", 650, "shift")
    stone.wait_for(result, lambda: control.call("inventory")["counts"].get(f"create:{result}", 0),
                   lambda count: count == 1)
    control.call("close")


def run(args):
    rows = reference("palettes")
    if {row["block"] for row in rows} != set(WINDOW_BLOCKS):
        raise RuntimeError("Java reference and pack window families differ.")
    pack = args.pack or ROOT / ".local/create.hmod"
    verify_pack(pack, args.java_source, rows)
    with fixture_world(args, "Window-palettes", pack=pack, render=True) as control:
        control.commands((
            "/fill 4 96 -13 11 96 -6 minecraft:smooth_stone",
            "/fill 4 97 -13 11 101 -6 minecraft:air",
            "/setblock 5 97 -11 minecraft:crafting_table",
            "/tp @s 6.25 97 -9.5",
            "/gamemode survival",
        ))
        for row in rows:
            wid = "create:" + row["block"]
            control.commands((
                "/setblock 8 97 -9 minecraft:air",
                f"/item replace entity @s hotbar.0 with {wid}",
            ))
            control.call("wait", 2)
            control.call("select", wid)
            control.call("interact", 8, 96, -9, "up")
            check_state(control, java_state(row["state"]))
            if control.call("inventory")["counts"].get(wid):
                raise RuntimeError(f"Placing {wid} did not consume the item")
        for row in reference("neighbors"):
            control.commands((
                "/setblock 9 97 -9 minecraft:air",
                f"/setblock 8 97 -9 {PANE}",
                f"/setblock 9 97 -9 {row['neighbor']}",
            ))
            check_state(control, java_state(row["state"]))
        control.commands((
            "/setblock 9 97 -9 minecraft:air",
            "/item replace entity @s hotbar.0 with minecraft:water_bucket",
        ))
        control.call("wait", 2)
        control.call("select", "minecraft:water_bucket")
        control.call("interact", *TARGET, "west")
        water, = reference("water")
        check_state(control, java_state(water["state"]))
        if control.call("inventory")["counts"].get("minecraft:bucket") != 1:
            raise RuntimeError("Waterlogging the pane did not return the empty bucket")
        craft(control, "create:oak_window", 2, (
            ("minecraft:oak_planks", (101, 103, 105)), ("minecraft:glass", (104,)),
        ))
        craft(control, PANE, 16, (("create:oak_window", (100, 101, 102, 103, 104, 105)),))
        control.command("/setblock 5 97 -11 minecraft:stonecutter")
        cut_glass(control, "glass", "framed_glass", "blocks")
        cut_glass(control, "glass_pane", "vertical_framed_glass_pane", "panes")
        if args.visual:
            control.commands((
                "/setblock 8 97 -9 minecraft:air",
                "/fill 8 97 -8 8 99 -4 create:oak_window",
                "/fill 8 97 -13 8 99 -10 create:birch_window_pane",
                "/tp @s 4.75 97 -8.5",
            ))
            control.call("look-at", 8.5, 98.4, -8.5)
            control.call("key", "f1", "tap")
            control.call("wait", 6)
            control.call("screenshot", ROOT / ".local/window-palettes.png")
    print(f"All {len(rows)} Java window and pane states matched real survival placement, alongside eight joins, bucket waterlogging, two crafting recipes and both stonecutting inputs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--java-source", type=Path)
    parser.add_argument("--visual", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
