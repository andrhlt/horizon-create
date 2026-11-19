#!/usr/bin/env python3
"""Find the Java clay-to-four-clay-balls Millstone recipe with R and U."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
ENV = {"CREATE_TEST_RECIPE_CATEGORIES": "1", "HORIZON_NO_AUDIO": "1"}


def panel(actor):
    return actor.call("create-test-recipe-panel")["panel"]


def run_player(actor, role):
    def wheat_recipe():
        categories = actor.call("create-test-recipe-categories")["categories"]
        milling = next(c for c in categories if c["id"] == "create:milling")
        return next((r for r in milling["recipes"] if any(
            s["item"] == "minecraft:wheat" for slot in r["inputs"] for s in slot)), None)
    wheat = mp.until("synced wheat milling category", wheat_recipe)
    assert [(o["stack"]["item"], o["stack"]["count"], o["chance"]) for o in wheat["outputs"]] == [
        ("create:wheat_flour", 1, 1.0), ("create:wheat_flour", 2, 0.25),
        ("minecraft:wheat_seeds", 1, 0.25)], wheat
    actor.call("key", "e", "tap")
    mp.until("inventory open", lambda: actor.call("screen")["screen"] == "inventory")
    def hover(item):
        slot = next(w for w in actor.call("ui")["widgets"] if w.get("stack") and w["stack"]["item"] == item)
        x, y, width, height = slot["bounds"]
        actor.call("scroll-at", x + width / 2, y + height / 2, 0)
    hover("minecraft:stone")
    actor.call("key", "r", "tap")
    actor.call("key", "u", "tap")
    assert panel(actor) is None
    for item, key in (("minecraft:clay_ball", "r"), ("minecraft:clay", "u")):
        hover(item)
        actor.call("key", key, "tap")
        view = mp.until(f"milling {key} panel", lambda: panel(actor))
        assert view["title"] == "Milling" and "create:millstone" in view["tabs"], view
        assert any("minecraft:clay" in slot and "minecraft:clay_ball" in recipe["outputs"]
                   and 4 in recipe["output_counts"]
                   for recipe in view["recipes"] for slot in recipe["inputs"]), view
        button = mp.until("Back button", lambda: next((w for w in actor.call("ui")["widgets"]
                          if w.get("label") == "Back" and w["enabled"]), None))
        actor.call("screenshot", ROOT / f".local/milling-lookup-{role}-{key}.png")
        actor.call("click", button["id"])
        mp.until("panel closed", lambda: panel(actor) is None)
    for item, key in (("create:wheat_flour", "r"), ("minecraft:wheat", "u")):
        hover(item)
        actor.call("key", key, "tap")
        view = mp.until(f"wheat {key} panel", lambda: panel(actor))
        wheat_view = next(r for r in view["recipes"] if any("minecraft:wheat" in slot for slot in r["inputs"]))
        assert wheat_view["outputs"] == ["create:wheat_flour", "create:wheat_flour", "minecraft:wheat_seeds"], wheat_view
        assert wheat_view["output_counts"] == [1, 2, 1], wheat_view
        assert wheat_view["chance_labels"] == ["100%", "25%", "25%"], wheat_view
        def output_widgets():
            widgets = actor.call("ui")["widgets"]
            labels = [w.get("label", "") for w in widgets]
            return widgets if any("Wheat Flour" in label for label in labels) and any("Wheat Seeds" in label for label in labels) and "25%" in labels and "100%" in labels else None
        widgets = mp.until("rendered wheat outputs and chances", output_widgets)
        actor.call("screenshot", ROOT / f".local/milling-wheat-{role}-{key}.png")
        button = next(w for w in widgets if w.get("label") == "Back" and w["enabled"])
        actor.call("click", button["id"])
        mp.until("wheat panel closed", lambda: panel(actor) is None)
    actor.call("key", "e", "tap")
    mp.until("inventory closed", lambda: actor.call("screen")["screen"] != "inventory")
    for key in ("r", "u"):
        actor.call("key", key, "tap")
    assert panel(actor) is None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="create-milling-lookup-") as tmp:
        with fixture_world(args, "MillingLookup", render=True, pack=args.pack, env=ENV) as host:
            host.commands(("/gamemode survival @s", "/clear @s",
                           "/item replace entity @s hotbar.0 with minecraft:clay_ball",
                           "/item replace entity @s hotbar.1 with minecraft:clay",
                           "/item replace entity @s hotbar.2 with minecraft:stone",
                           "/item replace entity @s hotbar.3 with minecraft:wheat",
                           "/item replace entity @s hotbar.4 with create:wheat_flour"))
            run_player(host, "solo")
            network = host.call("lan", "open", "0", "commands", "force")
            with mp.joined_client(args, Path(tmp), f"127.0.0.1:{network['port']}", "MillingGuest",
                                  render=True, env=ENV, pack=args.pack, scenario="milling-lookup") as guest:
                host.commands(("/gamemode survival MillingGuest", "/clear MillingGuest",
                               "/item replace entity MillingGuest hotbar.0 with minecraft:clay_ball",
                               "/item replace entity MillingGuest hotbar.1 with minecraft:clay",
                               "/item replace entity MillingGuest hotbar.2 with minecraft:stone",
                               "/item replace entity MillingGuest hotbar.3 with minecraft:wheat",
                               "/item replace entity MillingGuest hotbar.4 with create:wheat_flour"))
                mp.until("guest clay", lambda: guest.call("inventory")["counts"].get("minecraft:clay", 0) >= 1)
                run_player(guest, "guest")
    print("Millstone clay and wheat R/U lookup and Back passed in solo and LAN.")


if __name__ == "__main__":
    main()
