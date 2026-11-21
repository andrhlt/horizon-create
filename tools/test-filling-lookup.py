#!/usr/bin/env python3
"""Open representative Spout filling recipes with R/U in solo and LAN."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
ENV = {"CREATE_TEST_RECIPE_CATEGORIES": "1", "HORIZON_NO_AUDIO": "1"}


def panel(actor):
    return actor.call("create-test-recipe-panel")["panel"]


def hover(actor, item):
    slot = next(w for w in actor.call("ui")["widgets"]
                if w.get("stack") and w["stack"]["item"] == item)
    x, y, width, height = slot["bounds"]
    actor.call("scroll-at", x + width / 2, y + height / 2, 0)


def assert_honey_bottle(recipe):
    assert "minecraft:glass_bottle" in recipe["inputs"][0], recipe
    assert recipe["fluids"] == [{
        "slot": 1, "fluid": "create:honey", "amount": 250,
    }], recipe
    assert "minecraft:honey_bottle" in recipe["outputs"], recipe


def lookup(actor, role):
    actor.call("key", "e", "tap")
    mp.until("inventory open", lambda: actor.call("screen")["screen"] == "inventory")
    for item, key in (("minecraft:honey_bottle", "r"),
                      ("minecraft:glass_bottle", "u")):
        hover(actor, item)
        actor.call("key", key, "tap")
        view = mp.until("Filling recipe panel", lambda: panel(actor))
        assert view["title"] == "Filling", view
        assert "create:spout" in view["tabs"], view
        recipes = [r for r in view["recipes"] if "minecraft:honey_bottle" in r["outputs"]]
        assert recipes, view
        for recipe in recipes:
            assert_honey_bottle(recipe)
        fluid = mp.until("rendered 250 mB honey input", lambda: next((w for w in actor.call("ui")["widgets"]
                    if w.get("label") == "Honey 250 mB"), None))
        x, y, width, height = fluid["bounds"]
        actor.call("scroll-at", x + width / 2, y + height / 2, 0)
        back = mp.until("Back button", lambda: next((w for w in actor.call("ui")["widgets"]
                     if w.get("label") == "Back" and w["enabled"]), None))
        actor.call("screenshot", ROOT / f".local/filling-lookup-{role}-{key}.png")
        actor.call("click", back["id"])
        mp.until("recipe panel closes", lambda: panel(actor) is None)
    actor.call("key", "e", "tap")
    mp.until("inventory closes", lambda: actor.call("screen")["screen"] != "inventory")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="create-filling-lookup-") as tmp:
        with fixture_world(args, "FillingLookup", render=True, pack=args.pack, env=ENV) as host:
            def equip(target):
                host.commands((f"/gamemode survival {target}", f"/clear {target}",
                    f"/item replace entity {target} hotbar.0 with minecraft:honey_bottle",
                    f"/item replace entity {target} hotbar.1 with minecraft:glass_bottle"))

            equip("@s")
            lookup(host, "solo")
            host.restart()
            mp.until("saved lookup inputs after world reopen", lambda: all(
                host.call("inventory")["counts"].get(item, 0) >= 1
                for item in ("minecraft:honey_bottle", "minecraft:glass_bottle")))
            lookup(host, "reopened")
            network = host.call("lan", "open", "0", "commands", "force")
            with mp.joined_client(args, Path(tmp), f"127.0.0.1:{network['port']}", "FillingGuest",
                                  render=True, env=ENV, pack=args.pack, scenario="filling-lookup") as guest:
                equip("FillingGuest")
                mp.until("guest recipe inputs", lambda: guest.call("inventory")["counts"].get(
                    "minecraft:glass_bottle", 0) >= 1)
                lookup(guest, "guest")
    print("Spout filling recipe, honey amount, R/U navigation and Back passed in solo and LAN guest inventories.")


if __name__ == "__main__":
    main()
