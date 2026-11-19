#!/usr/bin/env python3
"""Find pinned Crushing Wheel recipes and switch from overlapping Milling."""
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
                     if c["id"] == "create:crushing" and c["recipes"]), None)
    crushing = mp.until("synced crushing category", category)
    assert any(s["item"] == "create:crushing_wheel" for s in crushing["catalysts"]), crushing
    gravel = [r for r in crushing["recipes"] if any(s["item"] == "minecraft:gravel" for slot in r["inputs"] for s in slot)]
    assert len(gravel) == 1, gravel  # Milling's gravel→flint is excluded by Java.
    outputs = gravel[0]["outputs"]
    assert [o["stack"]["item"] for o in outputs] == ["minecraft:sand", "minecraft:flint", "minecraft:clay_ball"], gravel
    assert all(abs(o["chance"] - expected) < 1e-6 for o, expected in zip(outputs, (1.0, 0.1, 0.05), strict=True)), gravel
    actor.call("key", "e", "tap")
    mp.until("inventory", lambda: actor.call("screen")["screen"] == "inventory")
    def hover(item):
        slot = next(w for w in actor.call("ui")["widgets"] if w.get("stack") and w["stack"]["item"] == item)
        x, y, width, height = slot["bounds"]
        actor.call("scroll-at", x + width / 2, y + height / 2, 0)
    def back():
        button = mp.until("Back", lambda: next((w for w in actor.call("ui")["widgets"] if w.get("label") == "Back"), None))
        actor.call("click", button["id"])
        mp.until("panel closed", lambda: page(actor) is None)
    for item, key in (("minecraft:cobblestone", "u"), ("minecraft:gravel", "r"), ("minecraft:gravel", "u")):
        hover(item)
        actor.call("key", key, "tap")
        initial = mp.until("initial category", lambda: page(actor))
        assert "create:crushing_wheel" in initial["tabs"] and "create:millstone" in initial["tabs"], initial
        wheel = mp.until("Crushing Wheel tab", lambda: next((w for w in actor.call("ui")["widgets"]
                         if w.get("label") == "Crushing Wheel tab"), None))
        actor.call("click", wheel["id"])
        view = mp.until("Crushing page", lambda: (v if (v := page(actor)) and v["title"] == "Crushing" else None))
        if item == "minecraft:gravel" and key == "u":
            recipe = next(r for r in view["recipes"] if any("minecraft:gravel" in slot for slot in r["inputs"]))
            assert recipe["outputs"] == ["minecraft:sand", "minecraft:flint", "minecraft:clay_ball"], recipe
            assert recipe["chance_labels"] == ["100%", "10%", "5%"], recipe
            labels = mp.until("crushing chance labels", lambda: (ws if (ws := actor.call("ui")["widgets"])
                          and {"100%", "10%", "5%"} <= {w.get("label") for w in ws} else None))
            actor.call("screenshot", ROOT / f".local/crushing-lookup-{role}.png")
        else:
            assert any("minecraft:cobblestone" in slot and "minecraft:gravel" in r["outputs"]
                       for r in view["recipes"] for slot in r["inputs"]), view
        back()
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
                       f"/item replace entity {target} hotbar.0 with minecraft:cobblestone",
                       f"/item replace entity {target} hotbar.1 with minecraft:gravel"))
    with TemporaryDirectory(prefix="create-crushing-lookup-") as tmp:
        with fixture_world(args, "CrushingLookup", render=True, pack=args.pack, env=ENV) as host:
            setup(host, "@s")
            player(host, "solo")
            network = host.call("lan", "open", "0", "commands", "force")
            with mp.joined_client(args, Path(tmp), f"127.0.0.1:{network['port']}", "CrushGuest",
                                  render=True, env=ENV, pack=args.pack, scenario="crushing-lookup") as guest:
                setup(host, "CrushGuest")
                mp.until("guest gravel", lambda: guest.call("inventory")["counts"].get("minecraft:gravel", 0) >= 1)
                player(guest, "guest")
    print("Crushing category, Milling overlap and chance outputs passed in solo and LAN.")


if __name__ == "__main__":
    main()
