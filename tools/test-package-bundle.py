#!/usr/bin/env python3
"""Compare Java package nesting through actual Horizon bundle and shulker menus."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


package = import_module("test-package-filter-editor")
filters = package.filters
editor = filters.editor
BUNDLE = "minecraft:bundle"


def attempt(host, actor, name, item, allowed, bundle_carried):
    host.commands((
        f"/clear {name}",
        f"/item replace entity {name} hotbar.0 with {BUNDLE}",
        f"/item replace entity {name} hotbar.1 with {item}",
    ))
    editor.wait_for(actor, "a bundle and the original item", lambda:
        actor.call("inventory")["counts"] == {BUNDLE:1, item:1}
    )
    actor.call("key", "e", "tap")
    editor.wait_for(actor, "the player's own inventory", lambda:
        actor.call("state")["screen"] == "inventory"
    )
    carry, destination = (0,1) if bundle_carried else (1,0)
    actor.call("click-slot", carry)
    original_cursor = BUNDLE if bundle_carried else item
    editor.wait_for(actor, "the real cursor stack", lambda:
        (actor.call("inventory").get("carried") or {}).get("item") == original_cursor
    )
    actor.call("click-slot", destination)
    actor.call("wait", 7)
    inventory = actor.call("inventory")
    hotbar = {entry["slot"]:entry for entry in inventory["hotbar"]}
    held = (inventory.get("carried") or {}).get("item")
    if bundle_carried:
        assert held == BUNDLE, (item, inventory)
        assert (hotbar[destination].get("item") == item) is (not allowed), (item, inventory)
    else:
        assert (held is None if allowed else held == item), (item, inventory)
    actor.call("close")
    editor.wait_for(actor, "the standard inventory to close", lambda:
        actor.call("state")["screen"] == "playing"
    )


def shulker(host, actor, name, item, allowed):
    block = (8, 101, -9)
    xyz = editor.xyz(block)
    host.commands((
        f"/clear {name}",
        f"/setblock {xyz} minecraft:air",
        f"/setblock {xyz} minecraft:shulker_box[facing=up]",
        f"/item replace entity {name} hotbar.1 with {item}",
    ))
    editor.wait_for(actor, "the package or original control in inventory", lambda:
        actor.call("inventory")["counts"] == {item: 1}
    )
    actor.call("interact", *block, "north")
    editor.wait_for(actor, "the placed shulker box to open", lambda:
        actor.call("state")["screen"] == "container"
    )
    actor.call("click-slot", 1)
    editor.wait_for(actor, "the item on the actual cursor", lambda:
        (actor.call("inventory").get("carried") or {}).get("item") == item
    )
    actor.call("click-slot", 300)
    actor.call("wait", 7)
    inventory = actor.call("inventory")
    held = (inventory.get("carried") or {}).get("item")
    contents = host.command(f"/data get block {xyz} Items")
    assert (held is None if allowed else held == item), (item, inventory)
    assert (f'"{item}"' in contents) == allowed, (item, contents)
    actor.call("close")
    editor.wait_for(actor, "the shulker box to close", lambda:
        actor.call("state")["screen"] == "playing"
    )


def run(args, scratch):
    with (ROOT / "fixtures/package-nesting-java.csv").open(newline="") as file:
        forms = list(csv.reader(file))
    assert len(forms) == 16
    with fixture_world(args, "PackageBundle", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 4 100 -14 16 100 -4 minecraft:smooth_stone",
            "/fill 4 101 -14 16 110 -4 minecraft:air",
            "/tp @s 8.5 101 -11.5 0 -80",
        ))
        with filters.actor_for(host, args, scratch if args.lan else None) as (actor, name):
            host.commands((f"/tp {name} 8.5 101 -11.5 0 0", f"/gamemode survival {name}"))
            editor.wait_for(actor, "the player beside the original shulker-box position", lambda:
                tuple(actor.call("state")["player"]["position"][:3]) == (8.5, 101, -11.5)
            )
            for item, bundle, shulker_slot in forms:
                for bundle_carried in (False, True):
                    attempt(host, actor, name, item, bundle == "true", bundle_carried)
                shulker(host, actor, name, item, shulker_slot == "true")
    print(f"{'Guest' if args.lan else 'Host'} matched 48 original Java bundle and shulker actions including all 14 package forms.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-package-bundle-") as scratch:
        run(args, Path(scratch))


if __name__ == "__main__":
    main()
