#!/usr/bin/env python3
"""Replay the original Copper Roof palette in Horizon survival."""
import argparse
from contextlib import ExitStack
import csv
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world
from prepare import model_references, upgrade_block_loot

mp = import_module("test-multiplayer")
palette = import_module("test-stone-palettes")
crafting = import_module("test-survival-crafting")
CUTTER = (8, 100, 22)
SLAB_SUPPORT = (12, 99, 22)
SLAB = (12, 100, 22)
WAXED_SLAB = "create:waxed_copper_shingle_slab"


def properties(row):
    return dict(part.split("=", 1) for part in row["state"].split("|") if part)


def audit_assets(pack, java, rows):
    generated = java / "src/generated/resources"
    resources = java / "src/main/resources"
    with ZipFile(pack) as archive:
        for row in rows:
            name = row["id"].removeprefix("create:")
            declared = json.loads(archive.read(f"data/create/horizon/block/{name}.json"))
            assert declared["item"], row
            definition = declared["properties"]
            assert (definition["hardness"], definition["explosion_resistance"], definition["requires_tool"]) == (
                float(row["hardness"]), float(row["resistance"]), row["requires_tool"] == "true",
            ), row
            loot = f"data/create/loot_table/blocks/{name}.json"
            expected = json.loads((generated / loot).read_bytes())
            upgrade_block_loot(expected)
            assert expected == json.loads(archive.read(loot)), loot
        asset_paths = [f"{folder}/{row['id'].removeprefix('create:')}.json"
                       for row in rows for folder in ("blockstates", "models/item")]
        checked = set()
        while asset_paths:
            relative = asset_paths.pop()
            if relative in checked:
                continue
            checked.add(relative)
            key = f"assets/create/{relative}"
            path = resources / key if (resources / key).is_file() else generated / key
            original = path.read_bytes()
            assert archive.read(key) == original, key
            if key.endswith(".json"):
                asset_paths.extend(model_references(json.loads(original)))
    print(f"Matched {len(rows)} block declarations and loot tables and {len(checked)} original asset files.", flush=True)


def examine_states(world, actor, rows):
    positions = tuple((4 + 2 * (i % 8), 100, 3 + 2 * (i // 8)) for i in range(len(rows)))
    world.commands(f"/setblock {' '.join(map(str, at))} {row['id']}"
                   for at, row in zip(positions, rows, strict=True))
    for player in (world,) if world is actor else (world, actor):
        for at, row in zip(positions, rows, strict=True):
            def matches_state():
                observed = player.call("block", *at)
                return observed["block"] == row["id"] and palette.state_properties(observed["state"]) == properties(row)
            mp.until(f"{row['id']} with the original default properties", matches_state)


def cut_copper(world, actor, name):
    actor.call("interact", *CUTTER, "up")
    palette.wait_for("the Stonecutter menu", lambda: actor.call("menu").get("station"),
                     lambda station: station == "Stonecutter")
    for part in ("shingles", "tiles"):
        world.command(f"/item replace entity {name} hotbar.0 with minecraft:copper_ingot")
        mp.until("the player to receive one copper ingot", lambda: mp.count(actor, "minecraft:copper_ingot") == 1)
        actor.call("click-slot", 0)
        actor.call("click-slot", 600)
        palette.selection(actor, f"create:copper_{part}_from_ingots_copper_stonecutting", None)
        actor.call("click-slot", 650, "shift")
        mp.until(f"two copper {part}", lambda: mp.count(actor, f"create:copper_{part}") == 2)
    actor.call("close")


def wax_slab(world, actor, name):
    world.commands((
        f"/item replace entity {name} hotbar.0 with create:copper_shingle_slab 2",
        f"/item replace entity {name} hotbar.1 with minecraft:honeycomb 2",
    ))
    mp.until("the player to receive both ingredients", lambda:
             mp.count(actor, "create:copper_shingle_slab") == 2 and mp.count(actor, "minecraft:honeycomb") == 2)
    actor.call("open-inventory")
    for slot in (0, 1):
        actor.call("click-slot", slot)
        actor.call("click-slot", 100 + slot)
    crafting.output(actor, WAXED_SLAB, 1)
    actor.call("click-slot", 200, "shift")
    mp.until("two waxed slabs to craft", lambda: mp.count(actor, WAXED_SLAB) == 2)
    slot = crafting.inventory_slot(actor, WAXED_SLAB)
    if slot > 8:
        actor.call("click-slot", slot)
        actor.call("click-slot", 0)
    actor.call("close")
    actor.call("select", WAXED_SLAB)
    actor.call("interact", *SLAB_SUPPORT, "up")
    palette.same_state(world, actor, SLAB, f"{WAXED_SLAB}[type=bottom,waterlogged=false]")
    actor.call("interact", *SLAB, "up")
    palette.same_state(world, actor, SLAB, f"{WAXED_SLAB}[type=double,waterlogged=false]")
    mp.until("both slabs to be consumed", lambda: mp.count(actor, WAXED_SLAB) == 0)


def main():
    parser = argparse.ArgumentParser()
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--java-source", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/copper-roof-blocks-java.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    if args.java_source:
        audit_assets(args.pack, args.java_source, rows)
    with ExitStack() as stack:
        scenario = "CopperRoofsLAN" if args.lan else "CopperRoofs"
        world = stack.enter_context(fixture_world(args, scenario, render=True, pack=args.pack))
        world.commands((
            "/fill 5 99 19 15 99 26 minecraft:smooth_stone",
            "/setblock 8 100 22 minecraft:stonecutter",
            "/tp @s 10.5 100 23.5",
        ))
        actor, name = world, "@s"
        if args.lan:
            world.command("/tp @s 14.5 100 25.5")
            name = "CopperGuest"
            port = world.call("lan", "open", 0, "commands", "force")["port"]
            folder = Path(stack.enter_context(TemporaryDirectory(prefix="hc-roof-")))
            actor = stack.enter_context(mp.joined_client(
                args, folder, f"127.0.0.1:{port}", name, render=True, scenario="copper-roofs", pack=args.pack,
            ))
            mp.until("the copper guest to join", lambda: any(
                guest["name"] == name and guest["placed"] for guest in world.call("lan", "status")["guests"]
            ))
            world.command(f"/tp {name} 10.5 100 23.5")
            mp.until("the copper guest to reach the stonecutter", lambda:
                     tuple(actor.call("state")["player"]["position"]) == (10.5, 100, 23.5))
            mp.until("the host to see the guest at the stonecutter", lambda: any(
                guest["name"] == name and tuple(guest["position"]) == (10.5, 100, 23.5)
                for guest in world.call("lan", "status")["guests"]
            ))
        world.command(f"/gamemode survival {name}")
        mp.until("the player to see the Stonecutter", lambda: actor.call("block", *CUTTER)["block"] == "minecraft:stonecutter")
        examine_states(world, actor, rows)
        cut_copper(world, actor, name)
        wax_slab(world, actor, name)
    print(f"Matched {len(rows)} default states, both original ingot stonecuts, and waxed slab crafting and placement.", flush=True)


if __name__ == "__main__":
    main()
