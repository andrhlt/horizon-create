#!/usr/bin/env python3
"""Exercise pressing category collection and host-to-guest recipe sync."""
import argparse
from importlib import import_module
import json
from pathlib import Path
import tempfile

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
ENV = {"CREATE_TEST_RECIPE_CATEGORIES": "1"}


def category(client):
    result = client.call("create-test-recipe-categories")
    return next(c for c in result["categories"] if c["id"] == "create:pressing")


def matching(cat, input_item, output_item):
    return [r for r in cat["recipes"] if any(
        s["item"] == input_item for slot in r["inputs"] for s in slot
    ) and any(o["stack"]["item"] == output_item for o in r["outputs"])]


def check(cat):
    assert cat["title"] == "Pressing", cat
    assert any(s["item"] == "create:mechanical_press" for s in cat["catalysts"]), cat
    iron = matching(cat, "minecraft:iron_ingot", "create:iron_sheet")
    assert iron, cat
    assert any(o["chance"] == 1 and o["min"] == 1 and o["max"] == 1
               for r in iron for o in r["outputs"] if o["stack"]["item"] == "create:iron_sheet"), iron
    for ingot, sheet in (
        ("minecraft:gold_ingot", "create:golden_sheet"),
        ("minecraft:copper_ingot", "create:copper_sheet"),
    ):
        recipes = matching(cat, ingot, sheet)
        assert recipes, f"Missing pressing route {ingot} -> {sheet}: {cat}"
    chance = matching(cat, "minecraft:diamond", "minecraft:gold_ingot")
    assert any(o["chance"] == 0.5 and o["min"] == 2 and o["max"] == 2
               for r in chance for o in r["outputs"] if o["stack"]["item"] == "minecraft:gold_ingot"), chance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="create-recipe-category-") as tmp:
        scratch = Path(tmp)
        with fixture_world(args, "PressingCategory", pack=args.pack, env=ENV) as host:
            game = Path(host._launch[host._launch.index("--game-dir") + 1])
            world = game / "saves/PressingCategory"
            pack = world / "datapacks/pressing-fixture"
            recipe = pack / "data/create/recipe/pressing/fixture_chance.json"
            recipe.parent.mkdir(parents=True)
            recipe.write_text(json.dumps({
                "type": "create:pressing", "ingredients": [{"item": "minecraft:diamond"}],
                "results": [{"id": "minecraft:gold_ingot", "count": 2, "chance": 0.5}],
            }))
            (pack / "pack.mcmeta").write_text('{"pack":{"description":"fixture"}}')
            (world / "datapacks.json").write_text('{"enabled":["vanilla","file/pressing-fixture"],"disabled":[]}')
            host.command("/reload")
            multiplayer.until("host category and synced recipes", lambda: matching(category(host), "minecraft:diamond", "minecraft:gold_ingot"))
            check(category(host))
            network = host.call("lan", "open", "0", "commands", "force")
            with multiplayer.joined_client(args, scratch, f"127.0.0.1:{network['port']}",
                                           "RecipeGuest", pack=args.pack, env=ENV,
                                           scenario="pressing-category") as guest:
                multiplayer.until("guest server recipes", lambda: matching(category(guest), "minecraft:diamond", "minecraft:gold_ingot"))
                check(category(guest))
                # The server's replacement must reach the existing guest: local
                # mod tags would incorrectly keep iron in this recipe.
                tag = pack / "data/c/tags/item/ingots/iron.json"
                tag.parent.mkdir(parents=True)
                tag.write_text(json.dumps({"replace": True, "values": ["minecraft:diamond"]}))
                host.command("/reload")
                multiplayer.until("guest replacement tag", lambda: matching(
                    category(guest), "minecraft:diamond", "create:iron_sheet"))
                assert not matching(category(guest), "minecraft:iron_ingot", "create:iron_sheet")
    print("Pressing category collection and host-to-guest recipe and tag sync passed.")


if __name__ == "__main__":
    main()
