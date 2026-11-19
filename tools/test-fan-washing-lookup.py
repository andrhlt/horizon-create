#!/usr/bin/env python3
"""Find Java's gravel bulk washing recipe and named fan catalyst."""
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
    def category():
        return next((c for c in actor.call("create-test-recipe-categories")["categories"]
                     if c["id"] == "create:fan_washing" and c["recipes"]), None)
    washing = mp.until("synced washing category", category)
    assert len(washing["catalysts"]) == 1 and washing["catalysts"][0]["item"] == "create:encased_fan", washing
    assert "Fan behind Flowing Water" in washing["catalysts"][0]["components"], washing
    assert "italic:false" in washing["catalysts"][0]["components"], washing
    gravel = next(r for r in washing["recipes"] if any(s["item"] == "minecraft:gravel" for slot in r["inputs"] for s in slot))
    assert [o["stack"]["item"] for o in gravel["outputs"]] == ["minecraft:flint", "minecraft:iron_nugget"], gravel
    assert all(abs(o["chance"] - x) < 1e-6 for o, x in zip(gravel["outputs"], (0.25, 0.125), strict=True)), gravel
    actor.call("key", "e", "tap")
    mp.until("inventory", lambda: actor.call("screen")["screen"] == "inventory")
    def hover(item):
        slot = next(w for w in actor.call("ui")["widgets"] if w.get("stack") and w["stack"]["item"] == item)
        x, y, width, height = slot["bounds"]
        actor.call("scroll-at", x + width / 2, y + height / 2, 0)
    for item, key in (("minecraft:gravel", "u"), ("minecraft:iron_nugget", "r")):
        hover(item)
        actor.call("key", key, "tap")
        initial = mp.until("recipe panel", lambda: page(actor))
        assert "create:encased_fan" in initial["tabs"], initial
        if initial["title"] != "Bulk Washing":
            fan = mp.until("Fan category tab", lambda: next((w for w in actor.call("ui")["widgets"]
                           if w.get("label") == "Encased Fan tab"), None))
            actor.call("click", fan["id"])
        view = mp.until("washing page", lambda: (v if (v := page(actor)) and v["title"] == "Bulk Washing" else None))
        recipe = next(r for r in view["recipes"] if any("minecraft:gravel" in slot for slot in r["inputs"]))
        assert recipe["outputs"] == ["minecraft:flint", "minecraft:iron_nugget"], recipe
        assert recipe["chance_labels"] == ["25%", "12.5%"], recipe
        labels = mp.until("washing output chances", lambda: (ws if (ws := actor.call("ui")["widgets"])
                          and {"25%", "12.5%"} <= {w.get("label") for w in ws} else None))
        fan = next(w for w in labels if w.get("label") == "Encased Fan tab")
        x, y, width, height = fan["bounds"]
        actor.call("scroll-at", x + width / 2, y + height / 2, 0)
        actor.call("screenshot", ROOT / f".local/fan-washing-lookup-{role}-{key}.png")
        back = next(w for w in actor.call("ui")["widgets"] if w.get("label") == "Back")
        actor.call("click", back["id"])
        mp.until("closed", lambda: page(actor) is None)
    actor.call("key", "e", "tap")
    mp.until("inventory closed", lambda: actor.call("screen")["screen"] != "inventory")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()
    def setup(host, target):
        host.commands((f"/gamemode survival {target}", f"/clear {target}",
                       f"/item replace entity {target} hotbar.0 with minecraft:gravel",
                       f"/item replace entity {target} hotbar.1 with minecraft:iron_nugget"))
    with TemporaryDirectory(prefix="create-washing-lookup-") as tmp:
        with fixture_world(args, "FanWashingLookup", render=True, pack=args.pack, env=ENV) as host:
            setup(host, "@s")
            player(host, "solo")
            network = host.call("lan", "open", "0", "commands", "force")
            with mp.joined_client(args, Path(tmp), f"127.0.0.1:{network['port']}", "WashGuest",
                                  render=True, env=ENV, pack=args.pack, scenario="fan-washing-lookup") as guest:
                setup(host, "WashGuest")
                mp.until("guest gravel", lambda: guest.call("inventory")["counts"].get("minecraft:gravel", 0) >= 1)
                player(guest, "guest")
    print("Bulk Washing category, named Fan and gravel R/U passed in solo and LAN.")


if __name__ == "__main__":
    main()
