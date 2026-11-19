#!/usr/bin/env python3
"""Replay the original Package Filter address editor through actual Horizon input."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import struct
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


filters = import_module("test-stockpile-switch-filter")
parsing = import_module("test-train-schedule-entry").snbt
wait_for = filters.editor.wait_for
ITEM = "create:package_filter"
ADDRESS = "create:package_address"
STONE = "minecraft:stone"
CHANGES = {1: "Workshop-East", 3: " Atelier Nord* ", 4: "   ", 5: "Shed-02"}


def saved(host, name):
    raw = host.command(f"/data get entity {name} Inventory")
    data = parsing(raw.split("entity data: ", 1)[1])
    stack = next((entry for entry in data if entry["id"] == ITEM), None)
    return stack.get("components", {}).get(ADDRESS) if stack else None


def expected(reference):
    return None if reference == "-" else bytes.fromhex(reference).decode()


def scope(actor, screenshot):
    actor.call("screenshot", screenshot)
    with screenshot.open("rb") as capture:
        width, height = struct.unpack(">II", capture.read(24)[16:24])
    return ((width / 2 - 218) // 2 - 11, (height / 2 - 191) // 2 + 7)


def point(origin, position):
    return tuple(a + b for a, b in zip(origin, position, strict=True))


def replace_text(actor, value):
    actor.call("key", "ctrl", "down")
    try:
        actor.call("key", "a", "tap")
    finally:
        actor.call("key", "ctrl", "up")
    actor.call("type", value)


def select_editor(actor):
    actor.call("mouse", "right", "click")
    wait_for(actor, "the Package Filter editor to open", lambda: actor.call("state")["screen"] == "mod")


def check_inventory(actor, origin):
    stone = point(origin, (85, 167))
    item = point(origin, (49, 167))
    actor.call("click-at", *stone)
    wait_for(actor, "the actual Stone stack on the cursor", lambda:
        (actor.call("inventory").get("carried") or {}).get("item") == STONE
    )
    actor.call("click-at", *item)
    assert actor.call("inventory")["held"]["item"] == ITEM
    actor.call("click-at", *stone)
    wait_for(actor, "the unchanged Stone stack back in its slot", lambda:
        actor.call("inventory")["counts"].get(STONE) == 4
        and actor.call("inventory").get("carried") is None
    )


def replay(host, actor, name, image, original):
    panel = None
    for scenario, before, after, holder, stone, valid in original:
        assert valid == "true"
        assert saved(host, name) == expected(before)
        select_editor(actor)
        if panel is None:
            panel = scope(actor, image)
            check_inventory(actor, panel)
        scenario = int(scenario)
        if scenario in CHANGES:
            replace_text(actor, CHANGES[scenario])
        if scenario == 6:
            actor.call("click-at", *point(panel, (164, 63)))
        if scenario in (0, 2):
            actor.call("key", "escape", "tap")
        else:
            actor.call("click-at", *point(panel, (194, 63)))
        wait_for(actor, "the Package Filter editor to close", lambda: actor.call("state")["screen"] == "playing")
        wait_for(actor, f"the original saved address at action {scenario}", lambda:
            saved(host, name) == expected(after)
        )
        assert actor.call("inventory")["counts"] == {ITEM: int(holder), STONE: int(stone)}
    select_editor(actor)
    replace_text(actor, "abcdefghijklmnopqrstuvwxyz")
    actor.call("click-at", *point(panel, (194, 63)))
    wait_for(actor, "the original 25-character address limit", lambda:
        saved(host, name) == "abcdefghijklmnopqrstuvwxy"
    )
    select_editor(actor)
    actor.call("click-at", *point(panel, (55, 32)), "right")
    actor.call("click-at", *point(panel, (194, 63)))
    wait_for(actor, "right click to clear the address field", lambda: saved(host, name) is None)


def verify(args, root, lan):
    with (ROOT / "fixtures/package-filter-editor-java.csv").open(newline="") as file:
        original = list(csv.reader(file))
    assert len(original) == 7
    with fixture_world(args, "PackageFilterEditor", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 5 100 -14 16 100 -4 minecraft:smooth_stone",
            "/fill 5 101 -14 16 109 -4 minecraft:air",
        ))
        with filters.actor_for(host, args, root if lan else None) as (actor, name):
            host.commands((
                f"/tp {name} 8.5 101 -9.5 0 -80",
                f"/gamemode survival {name}",
                f"/item replace entity {name} hotbar.0 with {ITEM}",
                f"/item replace entity {name} hotbar.2 with {STONE} 4",
            ))
            wait_for(actor, "the original main-hand filter and Stone arrangement", lambda:
                actor.call("inventory")["counts"] == {ITEM: 1, STONE: 4}
            )
            actor.call("select", ITEM)
            actor.call("options-set", "guiScale", "2")
            assert not actor.call("looking-at").get("block")
            replay(host, actor, name, root / "address-editor.png", original)
    print(f"{'Guest' if lan else 'Host'} matched seven original address saves, reopened settings, inventory custody and the typed bounds.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-pfe-") as scratch:
        verify(args, Path(scratch), args.lan)


if __name__ == "__main__":
    main()
