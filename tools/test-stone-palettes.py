#!/usr/bin/env python3
"""Compare the Java stone palettes with packed assets and survival play."""

import argparse
import csv
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world
from prepare import crafting_ingredient, model_references, upgrade_block_loot
from stone_palettes import (
    MATERIALS, PALETTE_BLOCKS, VANILLA_PALETTE_BLOCKS,
    normalize_recipe, palette_recipes, palette_tags,
)

multiplayer = import_module("test-multiplayer")

STONECUTTER = (5, 97, -9)


def check_pack(pack, rows, java, blocks, recipe_count):
    with ZipFile(pack) as archive:
        for row in rows:
            name = row["id"].removeprefix("create:")
            block = json.loads(archive.read(f"data/create/horizon/block/{name}.json"))
            if not block["item"]:
                raise RuntimeError(f"Missing block item for {row['id']}")
            for key, cast in (("hardness", float), ("resistance", float), ("map_color", int)):
                prop = "explosion_resistance" if key == "resistance" else key
                if block["properties"][prop] != cast(row[key]):
                    raise RuntimeError(f"Wrong {key} for {row['id']}: {block}")
            if block["properties"]["requires_tool"] != (row["requires_tool"] == "true"):
                raise RuntimeError(f"Wrong tool requirement for {row['id']}: {block}")

        if java is None:
            return
        roots = tuple(java / "src" / folder / "resources" for folder in ("main", "generated"))
        generated = roots[1]
        pending = [
            path for name in blocks for path in (
                f"blockstates/{name}.json", f"models/item/{name}.json",
            )
        ]
        checked = set()
        while pending:
            name = pending.pop()
            if name in checked:
                continue
            checked.add(name)
            relative = "assets/create/" + name
            source = next(root / relative for root in roots if (root / relative).is_file())
            original = source.read_bytes()
            if archive.read(relative) != original:
                raise RuntimeError(f"Different bytes for upstream asset {relative}")
            if name.endswith(".json"):
                pending.extend(model_references(json.loads(original)))

        for name in blocks:
            relative = f"data/create/loot_table/blocks/{name}.json"
            loot = json.loads((generated / relative).read_bytes())
            upgrade_block_loot(loot)
            if json.loads(archive.read(relative)) != loot:
                raise RuntimeError(f"Different block drops for {name}")

        ids = {row["id"] for row in rows}
        recipes = list(palette_recipes(generated, ids))
        if len(recipes) != recipe_count:
            raise RuntimeError(f"Expected {recipe_count} Java stone palette recipes, got {len(recipes)}")
        for relative, recipe in recipes:
            expected = normalize_recipe(recipe, crafting_ingredient)
            if json.loads(archive.read(str(relative))) != expected:
                raise RuntimeError(f"Stone palette recipe changed: {relative}")
        for relative, values in palette_tags(generated, ids):
            actual = json.loads(archive.read(str(relative)))["values"]
            if any(value not in actual for value in values):
                raise RuntimeError(f"Stone palette tag changed: {relative}")
        print(f"Matched {len(checked)} upstream model, blockstate and texture files, {len(rows)} loot tables, and {len(recipes)} recipes.")


def wait_for(description, read, ready):
    deadline = time.monotonic() + 4
    while True:
        value = read()
        if ready(value):
            return value
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Expected {description}, got {value}")
        time.sleep(0.05)


def selection(control, recipe, options_count):
    recipes = wait_for(
        f"{recipe} in the Stonecutter",
        lambda: (control.call("menu").get("info") or {}).get("recipes", []),
        lambda options: recipe in options and (options_count is None or len(options) == options_count),
    )
    index = recipes.index(recipe)
    control.call("wait", 2)
    nodes = control.call("ui")["widgets"]
    input_node = next(node for node in nodes if node["id"] == "slot-600")
    left, top, _, _ = input_node["bounds"]
    x, y = left - 20 + 60, top - 33 + 23
    if index >= 12:
        rows = index // 4 - 2
        control.call("scroll-at", x, y, -rows)
        index -= rows * 4
    control.call("click-at", x + (index % 4) * 16, y + (index // 4) * 18)


def cut(control, row, slot, options_count):
    family, base, count = row["family"], row["ingredient"], int(row["count"])
    control.call("click-slot", slot)
    wait_for(f"{base} on the cursor", lambda: control.call("menu").get("carried"),
             lambda stack: stack is not None and stack["item"] == base)
    control.call("click-slot", 600)
    part = f"cut_{family}_slab"
    selection(control, row["recipe"], options_count)

    def result():
        slots = control.call("menu")["slots"]
        return next((entry["stack"] for entry in slots if entry["slot"] == 650), None)

    wait_for(f"{count} {part} in the result", result,
             lambda stack: stack is not None and (stack["item"], stack["count"]) == (f"create:{part}", count))
    control.call("click-slot", 650, "shift")
    wait_for(f"{count} {part} in the inventory",
             lambda: control.call("inventory")["counts"].get(f"create:{part}", 0),
             lambda actual: actual == count)


def place_slabs(host, control, row):
    slab = f"create:cut_{row['family']}_slab"
    inventory = control.call("inventory")
    slot = next(entry["slot"] for entry in inventory["hotbar"] + inventory["main"]
                if entry.get("item") == slab)
    if slot >= 9:
        control.call("open-inventory")
        control.call("click-slot", slot)
        control.call("click-slot", 0)
        control.call("close")
    control.call("select", slab)
    host.command("/setblock 4 97 -7 minecraft:air")
    wait_for("the empty slab cell", lambda: control.call("block", 4, 97, -7)["block"],
             lambda block: block == "minecraft:air")
    control.call("interact", 4, 96, -7, "up")
    same_state(host, control, (4, 97, -7), f"{slab}[type={row['slab_first']},waterlogged=false]")
    control.call("interact", 4, 97, -7, "up")
    same_state(host, control, (4, 97, -7), f"{slab}[type={row['slab_second']},waterlogged=false]")
    wait_for("both slabs to be used", lambda: control.call("inventory")["counts"].get(slab, 0),
             lambda count: count == 0)


def same_state(host, actor, pos, expected):
    for control in (host,) if actor is host else (host, actor):
        wait_for(f"{expected} at {pos}", lambda: control.call("block", *pos)["state"],
                 lambda actual: actual == expected)


def state_properties(text):
    if "[" not in text:
        return {}
    return dict(part.split("=", 1) for part in text.split("[", 1)[1][:-1].split(","))


def exercise_building(host, actor, player, actions, option_count):
    host.commands((
        f"/tp {player} 3.0 97.0 -8.5 -90 20",
        f"/gamemode survival {player}",
    ))
    wait_for("the player at the Stonecutter", lambda: actor.call("state")["player"]["position"],
             lambda position: position == [3.0, 97.0, -8.5])
    for slot, row in enumerate(actions):
        base = row["ingredient"]
        host.command(f"/item replace entity {player} hotbar.{slot} with {base}")
        wait_for(base, lambda: actor.call("inventory")["counts"].get(base, 0),
                 lambda count: count == 1)
    actor.call("interact", *STONECUTTER, "up")
    wait_for("the Stonecutter screen", lambda: actor.call("menu").get("station"),
             lambda station: station == "Stonecutter")
    for slot, row in enumerate(actions):
        cut(actor, row, slot, option_count)
    actor.call("close")
    for row in actions:
        place_slabs(host, actor, row)

    host.command("/setblock 5 97 -9 minecraft:stone")
    for row in actions:
        if not row["pillar_axis"]:
            continue
        pillar = f"create:{row['family']}_pillar"
        host.commands((
            "/setblock 4 97 -9 minecraft:air",
            f"/item replace entity {player} hotbar.0 with {pillar}",
        ))
        wait_for(pillar, lambda: actor.call("inventory")["counts"].get(pillar, 0),
                 lambda count: count == 1)
        wait_for("a pillar target with a stone backing",
                 lambda: (actor.call("block", 4, 97, -9)["block"],
                          actor.call("block", 5, 97, -9)["block"]),
                 lambda blocks: blocks == ("minecraft:air", "minecraft:stone"))
        actor.call("select", pillar)
        actor.call("interact", 5, 97, -9, "west")
        same_state(host, actor, (4, 97, -9),
                   f"{pillar}[axis={row['pillar_axis']},east=false,north=false,south=false,west=false]")

    for row in actions:
        if not row["wall_east"]:
            continue
        family = row["family"]
        left, right = (8, 97, -9), (9, 97, -9)
        wall = f"create:cut_{family}_wall"
        host.commands((f"/setblock 8 97 -9 {wall}", f"/setblock 9 97 -9 {wall}"))
        for control in (host,) if actor is host else (host, actor):
            for pos, direction in ((left, "east"), (right, "west")):
                wait_for(f"{family} wall to join to the {direction}",
                         lambda: control.call("block", *pos)["state"],
                         lambda state: state.startswith(wall + "[")
                         and state_properties(state)[direction] == row[f"wall_{direction}"])


def run(args):
    if args.vanilla:
        blocks, recipes, option_count = VANILLA_PALETTE_BLOCKS, 238, None
        reference = "vanilla-stone-palette-blocks-java.csv"
        with (ROOT / "fixtures/vanilla-stone-palette-actions-java.csv").open() as source:
            actions = list(csv.DictReader(source))
    else:
        blocks, recipes, option_count = PALETTE_BLOCKS, 245, 19
        reference = "stone-palette-blocks-java.csv"
        actions = [{
            "family": family, "ingredient": f"create:{family}",
            "recipe": f"create:cut_{family}_slab_from_stone_types_{family}_stonecutting",
            "count": 2, "slab_first": "bottom", "slab_second": "double",
            "pillar_axis": "x" if family == "ochrum" else "",
            "wall_east": "low" if family == "scoria" else "", "wall_west": "low",
        } for family in MATERIALS]
    with (ROOT / "fixtures" / reference).open() as source:
        rows = list(csv.DictReader(source))
    if {row["id"] for row in rows} != {f"create:{name}" for name in blocks}:
        raise RuntimeError("The Java palette registry and the generated palette names differ")
    pack = args.pack or ROOT / ".local/create.hmod"
    check_pack(pack, rows, args.java_source, blocks, recipes)
    results = []
    with fixture_world(args, "Stone-palettes", pack=pack, render=True) as host:
        host.commands((
            "/fill 3 96 -11 12 96 -6 minecraft:smooth_stone",
            "/fill 3 97 -11 12 100 -6 minecraft:air",
            "/setblock 5 97 -9 minecraft:stonecutter",
        ))
        if not args.lan:
            for i, row in enumerate(rows):
                block = row["id"]
                x, y, z = 3 + (i % 12) * 3, 99, 3 + (i // 12) * 3
                changed, item = host.commands((
                    f"/setblock {x} {y} {z} {block}",
                    f"/clear @s {block} 0",
                ))
                actual = host.call("block", x, y, z)
                expected = dict(prop.split("=", 1) for prop in row["default_state"].split(";") if prop)
                if (actual["block"] != block or state_properties(actual["state"]) != expected
                        or not item.startswith("No items were found")):
                    raise RuntimeError(f"Mismatch for {block}: {changed}, {item}, {actual}")
                results.append((block, actual["state"]))
            exercise_building(host, host, "@s", actions, option_count)
        else:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            player = "StoneGuest"
            with TemporaryDirectory(prefix="hc-ston-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", player, render=True,
                scenario="stone-palettes", pack=pack,
            ) as guest:
                multiplayer.until("the stone palette guest to join", lambda: any(
                    p["name"] == player and p["placed"] for p in host.call("lan", "status")["guests"]
                ))
                exercise_building(host, guest, player, actions, option_count)
    if args.lan:
        print(f"The survival guest crafted and placed the {len(actions)} families on live LAN.")
        return
    trace = ROOT / ".local" / reference.replace("-java", "-horizon")
    with trace.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(("id", "state"))
        writer.writerows(results)
    print(f"Placed all {len(results)} original blocks with matching default states and cut and placed every family in survival.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-source", type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--vanilla", action="store_true")
    parser.add_argument("--lan", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())
