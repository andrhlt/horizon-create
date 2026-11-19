#!/usr/bin/env python3
"""Switch copper ingot uses between pressing and heated mixing."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

mp = import_module("test-multiplayer")
ENV = {"CREATE_TEST_RECIPE_CATEGORIES": "1", "HORIZON_NO_AUDIO": "1"}


def page(actor):
    return actor.call("create-test-recipe-panel")["panel"]


def player(actor, role):
    actor.call("key", "e", "tap")
    mp.until("inventory", lambda: actor.call("screen")["screen"] == "inventory")
    slot = next(w for w in actor.call("ui")["widgets"] if w.get("stack") and w["stack"]["item"] == "minecraft:copper_ingot")
    x, y, width, height = slot["bounds"]
    actor.call("scroll-at", x + width / 2, y + height / 2, 0)
    actor.call("key", "u", "tap")
    view = mp.until("copper uses", lambda: page(actor))
    assert view["title"] == "Pressing" and view["tabs"] == ["create:mechanical_press", "create:mechanical_mixer"], view
    assert any("create:copper_sheet" in r["outputs"] for r in view["recipes"]), view
    mixer = mp.until("Mixer category tab", lambda: next((w for w in actor.call("ui")["widgets"]
                     if w.get("label") == "Mechanical Mixer tab"), None))
    actor.call("click", mixer["id"])
    view = mp.until("mixing category", lambda: (v if (v := page(actor)) and v["title"] == "Mixing" else None))
    assert any("minecraft:copper_ingot" in r["inputs"][0] and "create:zinc_ingot" in r["inputs"][1]
               and "create:brass_ingot" in r["outputs"] and "Heated" in r["note"] and "Basin" in r["note"]
               for r in view["recipes"]), view
    actor.call("screenshot", ROOT / f".local/copper-uses-{role}.png")
    press = mp.until("Press category tab", lambda: next((w for w in actor.call("ui")["widgets"]
                     if w.get("label") == "Mechanical Press tab"), None))
    actor.call("click", press["id"])
    mp.until("back to pressing", lambda: (v := page(actor)) and v["title"] == "Pressing")
    back = mp.until("Back", lambda: next((w for w in actor.call("ui")["widgets"] if w.get("label") == "Back"), None))
    actor.call("click", back["id"])
    mp.until("closed", lambda: page(actor) is None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="create-recipe-navigation-") as tmp:
        with fixture_world(args, "CopperUses", render=True, pack=args.pack, env=ENV) as host:
            host.commands(("/gamemode survival @s", "/clear @s", "/item replace entity @s hotbar.0 with minecraft:copper_ingot"))
            player(host, "solo")
            host.call("key", "e", "tap")
            network = host.call("lan", "open", "0", "commands", "force")
            with mp.joined_client(args, Path(tmp), f"127.0.0.1:{network['port']}", "CopperGuest",
                                  render=True, env=ENV, pack=args.pack, scenario="recipe-navigation") as guest:
                host.commands(("/gamemode survival CopperGuest", "/clear CopperGuest", "/item replace entity CopperGuest hotbar.0 with minecraft:copper_ingot"))
                mp.until("guest copper", lambda: guest.call("inventory")["counts"].get("minecraft:copper_ingot", 0) >= 1)
                player(guest, "guest")
    print("Copper uses category navigation passed in solo and LAN.")


if __name__ == "__main__":
    main()
