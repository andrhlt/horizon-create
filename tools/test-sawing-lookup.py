#!/usr/bin/env python3
"""Find Create's bamboo cutting recipe with real R/U inventory input."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
ENV = {"CREATE_TEST_RECIPE_CATEGORIES": "1", "HORIZON_NO_AUDIO": "1"}


def panel(actor):
    return actor.call("create-test-recipe-panel")["panel"]


def player(actor, role):
    def category():
        categories = actor.call("create-test-recipe-categories")["categories"]
        return next((c for c in categories if c["id"] == "create:sawing" and c["recipes"]), None)
    saw = mp.until("synced sawing category", category)
    assert any(s["item"] == "create:mechanical_saw" for s in saw["catalysts"]), saw
    recipes = [r for r in saw["recipes"] if any(s["item"] == "minecraft:bamboo_planks"
               for slot in r["inputs"] for s in slot)]
    assert any(o["stack"]["item"] == "minecraft:bamboo_mosaic" and o["stack"]["count"] == 1
               and o["chance"] == 1.0 for r in recipes for o in r["outputs"]), recipes
    actor.call("key", "e", "tap")
    mp.until("inventory", lambda: actor.call("screen")["screen"] == "inventory")
    def hover(item):
        slot = next(w for w in actor.call("ui")["widgets"] if w.get("stack") and w["stack"]["item"] == item)
        x, y, width, height = slot["bounds"]
        actor.call("scroll-at", x + width / 2, y + height / 2, 0)
    hover("minecraft:stone")
    for key in ("r", "u"):
        actor.call("key", key, "tap")
    assert panel(actor) is None
    for item, key in (("minecraft:bamboo_mosaic", "r"), ("minecraft:bamboo_planks", "u")):
        hover(item)
        actor.call("key", key, "tap")
        view = mp.until(f"sawing {key} panel", lambda: panel(actor))
        assert view["title"] == "Sawing" and "create:mechanical_saw" in view["tabs"], view
        assert any("minecraft:bamboo_planks" in slot and "minecraft:bamboo_mosaic" in r["outputs"]
                   for r in view["recipes"] for slot in r["inputs"]), view
        button = mp.until("Back button", lambda: next((w for w in actor.call("ui")["widgets"]
                          if w.get("label") == "Back" and w["enabled"]), None))
        actor.call("screenshot", ROOT / f".local/sawing-lookup-{role}-{key}.png")
        actor.call("click", button["id"])
        mp.until("panel closed", lambda: panel(actor) is None)
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
    with TemporaryDirectory(prefix="create-sawing-lookup-") as tmp:
        with fixture_world(args, "SawingLookup", render=True, pack=args.pack, env=ENV) as host:
            host.commands(("/gamemode survival @s", "/clear @s",
                           "/item replace entity @s hotbar.0 with minecraft:bamboo_mosaic",
                           "/item replace entity @s hotbar.1 with minecraft:bamboo_planks",
                           "/item replace entity @s hotbar.2 with minecraft:stone"))
            player(host, "solo")
            network = host.call("lan", "open", "0", "commands", "force")
            with mp.joined_client(args, Path(tmp), f"127.0.0.1:{network['port']}", "SawGuest",
                                  render=True, env=ENV, pack=args.pack, scenario="sawing-lookup") as guest:
                host.commands(("/gamemode survival SawGuest", "/clear SawGuest",
                               "/item replace entity SawGuest hotbar.0 with minecraft:bamboo_mosaic",
                               "/item replace entity SawGuest hotbar.1 with minecraft:bamboo_planks",
                               "/item replace entity SawGuest hotbar.2 with minecraft:stone"))
                mp.until("guest bamboo", lambda: guest.call("inventory")["counts"].get("minecraft:bamboo_planks", 0) >= 1)
                player(guest, "guest")
    print("Sawing bamboo recipe R/U lookup and Back passed in solo and LAN.")


if __name__ == "__main__":
    main()
