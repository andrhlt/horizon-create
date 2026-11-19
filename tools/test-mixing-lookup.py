#!/usr/bin/env python3
"""Find pinned dry Mixer recipes and heat requirements with real R/U input."""
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
        return next((c for c in actor.call("create-test-recipe-categories")["categories"]
                     if c["id"] == "create:mixing" and c["recipes"]), None)
    mixing = mp.until("synced dry mixing category", category)
    assert {s["item"] for s in mixing["catalysts"]} == {"create:mechanical_mixer", "create:basin"}, mixing
    dough = next(r for r in mixing["recipes"] if any(o["stack"]["item"] == "create:dough" for o in r["outputs"]))
    assert dough["fluids"] == [{"slot": 1, "fluid": "minecraft:water", "amount": 1000}], dough
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
    cases = (
        ("create:andesite_alloy", "r", ("minecraft:andesite", "minecraft:iron_nugget"), "create:andesite_alloy", 1, "No Heating Required"),
        ("minecraft:iron_nugget", "u", ("minecraft:andesite", "minecraft:iron_nugget"), "create:andesite_alloy", 1, "No Heating Required"),
        ("create:brass_ingot", "r", ("minecraft:copper_ingot", "create:zinc_ingot"), "create:brass_ingot", 2, "Heated"),
        ("create:zinc_ingot", "u", ("minecraft:copper_ingot", "create:zinc_ingot"), "create:brass_ingot", 2, "Heated"),
        ("create:dough", "r", ("create:wheat_flour",), "create:dough", 1, "No Heating Required"),
        ("create:wheat_flour", "u", ("create:wheat_flour",), "create:dough", 1, "No Heating Required"),
    )
    for item, key, inputs, output, count, note in cases:
        hover(item)
        actor.call("key", key, "tap")
        view = mp.until(f"mixing {key} {item}", lambda: panel(actor))
        assert view["title"] == "Mixing" and "create:mechanical_mixer" in view["tabs"], view
        assert "create:basin" in view["tabs"] or "create:encased_fan" in view["tabs"], view
        assert any(all(any(ingredient in slot for slot in r["inputs"]) for ingredient in inputs)
                   and output in r["outputs"] and count in r["output_counts"] and note in r["note"]
                   and ("create:basin" in view["tabs"] or "Basin" in r["note"])
                   for r in view["recipes"]), view
        if output == "create:dough":
            dough_view = next(r for r in view["recipes"] if "create:dough" in r["outputs"])
            assert dough_view["fluids"] == [{"slot": 1, "fluid": "minecraft:water", "amount": 1000}], dough_view
            water = mp.until("rendered water slot", lambda: next((w for w in actor.call("ui")["widgets"]
                             if w.get("label") == "Water 1000 mB"), None))
            x, y, width, height = water["bounds"]
            actor.call("scroll-at", x + width / 2, y + height / 2, 0)
        button = mp.until("Back button", lambda: next((w for w in actor.call("ui")["widgets"]
                          if w.get("label") == "Back" and w["enabled"]), None))
        actor.call("screenshot", ROOT / f".local/mixing-lookup-{role}-{item.split(':')[1]}-{key}.png")
        actor.call("click", button["id"])
        mp.until("panel closed", lambda: panel(actor) is None)
    hover("minecraft:honey_block")
    actor.call("key", "u", "tap")
    view = mp.until("honey mixing panel", lambda: panel(actor))
    honey = next(r for r in view["recipes"] if any("minecraft:honey_block" in slot for slot in r["inputs"]))
    assert honey["fluid_outputs"] == [{"slot": 1, "fluid": "create:honey", "amount": 1000}], honey
    assert honey["note"] == "Heated", honey
    honey_slot = mp.until("rendered honey slot", lambda: next((w for w in actor.call("ui")["widgets"]
                         if w.get("label") == "Honey 1000 mB"), None))
    x, y, width, height = honey_slot["bounds"]
    actor.call("scroll-at", x + width / 2, y + height / 2, 0)
    button = mp.until("Back button", lambda: next((w for w in actor.call("ui")["widgets"]
                      if w.get("label") == "Back" and w["enabled"]), None))
    actor.call("screenshot", ROOT / f".local/mixing-honey-{role}.png")
    actor.call("click", button["id"])
    mp.until("honey panel closed", lambda: panel(actor) is None)
    for item, fluid, amount, note, label in (
        ("create:bar_of_chocolate", "create:chocolate", 250, "Heated", "Chocolate"),
        ("minecraft:mossy_cobblestone", "minecraft:lava", 50, "Super-Heated", "Lava"),
    ):
        hover(item)
        actor.call("key", "u", "tap")
        view = mp.until(f"{label} mixing panel", lambda: panel(actor))
        recipe = next(r for r in view["recipes"] if any(item in slot for slot in r["inputs"]))
        assert recipe["fluid_outputs"] == [{"slot": 1, "fluid": fluid, "amount": amount}], recipe
        assert recipe["note"] == note, recipe
        fluid_slot = mp.until(f"rendered {label} slot", lambda: next((w for w in actor.call("ui")["widgets"]
                              if w.get("label") == f"{label} {amount} mB"), None))
        x, y, width, height = fluid_slot["bounds"]
        actor.call("scroll-at", x + width / 2, y + height / 2, 0)
        button = mp.until("Back button", lambda: next((w for w in actor.call("ui")["widgets"]
                          if w.get("label") == "Back" and w["enabled"]), None))
        actor.call("screenshot", ROOT / f".local/mixing-{label.lower()}-{role}.png")
        actor.call("click", button["id"])
        mp.until(f"{label} panel closed", lambda: panel(actor) is None)
    actor.call("key", "e", "tap")
    mp.until("inventory closed", lambda: actor.call("screen")["screen"] != "inventory")
    actor.call("key", "u", "tap")
    assert panel(actor) is None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()
    items = ("create:andesite_alloy", "minecraft:iron_nugget", "create:brass_ingot", "create:zinc_ingot", "minecraft:stone", "create:dough", "create:wheat_flour", "minecraft:honey_block", "create:bar_of_chocolate", "minecraft:mossy_cobblestone")
    def setup(host, target):
        host.commands((f"/gamemode survival {target}", f"/clear {target}",
                       *(f"/item replace entity {target} {('hotbar.' + str(i)) if i < 9 else ('inventory.' + str(i - 9))} with {item}" for i, item in enumerate(items))))
    with TemporaryDirectory(prefix="create-mixing-lookup-") as tmp:
        with fixture_world(args, "MixingLookup", render=True, pack=args.pack, env=ENV) as host:
            setup(host, "@s")
            player(host, "solo")
            network = host.call("lan", "open", "0", "commands", "force")
            with mp.joined_client(args, Path(tmp), f"127.0.0.1:{network['port']}", "MixerGuest",
                                  render=True, env=ENV, pack=args.pack, scenario="mixing-lookup") as guest:
                setup(host, "MixerGuest")
                mp.until("guest ingredients", lambda: guest.call("inventory")["counts"].get("create:zinc_ingot", 0) >= 1)
                player(guest, "guest")
    print("Mixer R/U, item and fluid slots, catalysts, heat and Back passed in solo and LAN.")


if __name__ == "__main__":
    main()
