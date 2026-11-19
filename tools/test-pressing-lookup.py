#!/usr/bin/env python3
"""Open pressing recipes and uses from inventory with the R and U keys."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
ENV = {"CREATE_TEST_RECIPE_CATEGORIES": "1", "HORIZON_NO_AUDIO": "1"}


def panel(actor):
    return actor.call("create-test-recipe-panel")["panel"]


def run_player(actor, name):
    actor.call("key", "e", "tap")
    mp.until("inventory open", lambda: actor.call("screen")["screen"] == "inventory")
    def slot(item):
        return next(w for w in actor.call("ui")["widgets"] if w.get("stack") and w["stack"]["item"] == item)
    def hover(item):
        x, y, width, height = slot(item)["bounds"]
        actor.call("scroll-at", x + width / 2, y + height / 2, 0)
    hover("minecraft:stone")
    actor.call("key", "r", "tap")
    actor.call("key", "u", "tap")
    assert panel(actor) is None
    hover("create:iron_sheet")
    actor.call("key", "r", "tap")
    view = mp.until("pressing recipe panel", lambda: panel(actor))
    assert view["title"] == "Pressing", view
    assert "create:mechanical_press" in view["tabs"], view
    assert any("minecraft:iron_ingot" in slot and "create:iron_sheet" in recipe["outputs"]
               for recipe in view["recipes"] for slot in recipe["inputs"]), view
    def back():
        return next((w for w in actor.call("ui")["widgets"] if w.get("label") == "Back" and w["enabled"]), None)
    button = mp.until("rendered Back button", back)
    actor.call("screenshot", ROOT / f".local/pressing-lookup-{name}.png")
    actor.call("click", button["id"])
    mp.until("recipe panel closes", lambda: panel(actor) is None)
    hover("minecraft:iron_ingot")
    actor.call("key", "u", "tap")
    view = mp.until("pressing uses panel", lambda: panel(actor))
    assert "create:mechanical_press" in view["tabs"], view
    assert any("minecraft:iron_ingot" in slot and "create:iron_sheet" in recipe["outputs"]
               for recipe in view["recipes"] for slot in recipe["inputs"]), view
    button = mp.until("rendered uses Back button", back)
    actor.call("screenshot", ROOT / f".local/pressing-uses-{name}.png")
    actor.call("click", button["id"])
    mp.until("uses panel closes", lambda: panel(actor) is None)
    actor.call("key", "e", "tap")
    mp.until("inventory closes", lambda: actor.call("screen")["screen"] != "inventory")
    actor.call("key", "r", "tap")
    actor.call("key", "u", "tap")
    assert panel(actor) is None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="create-pressing-lookup-") as tmp:
        with fixture_world(args, "PressingLookup", render=True, pack=args.pack, env=ENV) as host:
            host.commands(("/gamemode survival @s", "/clear @s",
                           "/item replace entity @s hotbar.0 with create:iron_sheet",
                           "/item replace entity @s hotbar.1 with minecraft:stone",
                           "/item replace entity @s hotbar.2 with minecraft:iron_ingot"))
            run_player(host, "solo")
            host.commands(("/fill 3 169 16 7 169 21 minecraft:stone",
                           "/setblock 5 170 20 minecraft:chest", "/tp @s 5.5 170 18.5"))
            mp.until("player reaches chest", lambda: host.call("state")["player"]["position"] == [5.5, 170.0, 18.5])
            host.call("interact", 5, 170, 20, "north")
            mp.until("chest open", lambda: host.call("screen")["screen"] == "container")
            sheet = next(w for w in host.call("ui")["widgets"]
                         if w.get("stack") and w["stack"]["item"] == "create:iron_sheet")
            x, y, width, height = sheet["bounds"]
            host.call("scroll-at", x + width / 2, y + height / 2, 0)
            host.call("key", "r", "tap")
            ingot = next(w for w in host.call("ui")["widgets"]
                         if w.get("stack") and w["stack"]["item"] == "minecraft:iron_ingot")
            x, y, width, height = ingot["bounds"]
            host.call("scroll-at", x + width / 2, y + height / 2, 0)
            host.call("key", "u", "tap")
            assert panel(host) is None
            host.call("key", "escape", "tap")
            network = host.call("lan", "open", "0", "commands", "force")
            with mp.joined_client(args, Path(tmp), f"127.0.0.1:{network['port']}", "LookupGuest",
                                  render=True, env=ENV, pack=args.pack, scenario="pressing-lookup") as guest:
                host.commands(("/gamemode survival LookupGuest", "/clear LookupGuest",
                               "/item replace entity LookupGuest hotbar.0 with create:iron_sheet",
                               "/item replace entity LookupGuest hotbar.1 with minecraft:stone",
                               "/item replace entity LookupGuest hotbar.2 with minecraft:iron_ingot"))
                mp.until("guest inventory", lambda: guest.call("inventory")["counts"].get("create:iron_sheet", 0) >= 1)
                run_player(guest, "guest")
    print("Pressing recipe and uses lookup and Back passed in solo and LAN guest inventories.")


if __name__ == "__main__":
    main()
