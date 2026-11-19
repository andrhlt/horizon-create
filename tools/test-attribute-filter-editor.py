#!/usr/bin/env python3
"""Replay the original Attribute Filter's ordinary reference and selection controls."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from shutil import which
from subprocess import check_output
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


list_filter = import_module("test-list-filter-editor")
package = list_filter.package
filters = package.filters
editor = filters.editor
ITEM = "create:attribute_filter"
REFERENCE = "minecraft:apple"
STONE = "minecraft:stone"
MODE = "create:attribute_filter_whitelist_mode"
ATTRIBUTES = "create:attribute_filter_matched_attributes"


def panel_position(actor, image):
    actor.call("screenshot", image)
    width, height = list_filter.dimensions(image)
    return ((width / 2 - 241) // 2 - 11, (height / 2 - 197) // 2 + 7)


def reference_pixels(ffmpeg, image, panel):
    left, top = package.point(panel, (16, 27))
    return check_output((ffmpeg, "-v", "error", "-i", str(image), "-vf",
                         f"crop=32:32:{left*2:.0f}:{top*2:.0f}",
                         "-pix_fmt", "rgb24", "-f", "rawvideo", "-"))


def open_editor(actor):
    actor.call("mouse", "right", "click")
    editor.wait_for(actor, "the original Attribute Filter screen", lambda:
        actor.call("state")["screen"] == "mod"
    )


def saved(host, name):
    raw = host.command(f"/data get entity {name} SelectedItem")
    result = package.parsing(raw.split("entity data: ", 1)[1])
    assert result["id"] == ITEM, result
    return result.get("components", {})


def verify_saved(host, name, row):
    action, reference, placeholder, holder, apples, stone, mode, count, valid, *original_matches = row
    assert valid == "true" and placeholder == "1"
    assert original_matches == ["false", "false"]
    state = saved(host, name)
    if mode == "null":
        assert MODE not in state and ATTRIBUTES not in state, (action, state)
    else:
        assert state[MODE] == mode.lower(), (action, state)
        assert len(state[ATTRIBUTES]) == int(count), (action, state)
        selected = [(a["attribute"]["type"], bool(a["inverted"])) for a in state[ATTRIBUTES]]
        assert selected == [("create:consumable", False), ("create:compostable", True)], (action, selected)


def run(args, scratch):
    with (ROOT / "fixtures/attribute-filter-editor-java.csv").open(newline="") as file:
        rows = list(csv.reader(file))
    assert len(rows) == 6
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to verify the rendered reference item.")
    screenshot = scratch/"attribute-editor.png"
    with fixture_world(args, "AttributeFilterEditor", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 5 100 -14 16 100 -4 minecraft:smooth_stone",
            "/fill 5 101 -14 16 109 -4 minecraft:air",
        ))
        with filters.actor_for(host, args, scratch if args.lan else None) as (actor, name):
            host.commands((
                f"/tp {name} 8.5 101 -9.5 0 -80",
                f"/gamemode survival {name}",
                f"/item replace entity {name} hotbar.0 with {ITEM}",
                f"/item replace entity {name} hotbar.1 with {REFERENCE} 5",
                f"/item replace entity {name} hotbar.2 with {STONE} 3",
            ))
            editor.wait_for(actor, "the filter and reference stacks to arrive", lambda:
                actor.call("inventory")["counts"] == {ITEM:1, REFERENCE:5, STONE:3}
            )
            actor.call("select", ITEM)
            actor.call("options-set", "guiScale", "2")
            open_editor(actor)
            panel = panel_position(actor, screenshot)
            empty = reference_pixels(ffmpeg, screenshot, panel)
            click = lambda xy, **kwargs: list_filter.click(actor, panel, xy, **kwargs)

            for row in rows:
                action = row[0]
                if action == "reference":
                    click((75, 172), shift=True)
                    actor.call("wait", 5)
                if action == "save":
                    click((191, 35))
                    actor.call("scroll-at", *package.point(panel, (100, 34)), 1)
                    actor.call("wait", 5)
                    click((209, 35))
                    click((65, 70))
                    click((217, 70))
                    editor.wait_for(host, "the two selected attributes to save", lambda:
                        len(saved(host, name).get(ATTRIBUTES, [])) == 2
                    )
                if action == "reopen":
                    editor.wait_for(actor, "the Attribute Filter to have closed", lambda:
                        actor.call("state")["screen"] == "playing"
                    )
                    open_editor(actor)
                if action == "deny":
                    click((83, 70))
                    click((217, 70))
                    editor.wait_for(host, "the deny mode to save", lambda:
                        saved(host, name).get(MODE) == "blacklist"
                    )
                if action == "reset":
                    editor.wait_for(actor, "the Attribute Filter to have closed", lambda:
                        actor.call("state")["screen"] == "playing"
                    )
                    open_editor(actor)
                    click((188, 70))
                    click((47, 70))
                    click((217, 70))
                    editor.wait_for(host, "the attributes and default mode to clear", lambda:
                        MODE not in saved(host, name)
                    )
                if actor.call("state")["screen"] == "mod":
                    actor.call("screenshot", screenshot)
                    actual = reference_pixels(ffmpeg, screenshot, panel)
                    changed = sum(abs(a-b) > 15 for a,b in zip(actual, empty, strict=True)) > 45
                    assert changed == (row[1] == "1"), (action, changed)
                verify_saved(host, name, row)
                counts = actor.call("inventory")["counts"]
                assert counts == {ITEM: int(row[3]), REFERENCE: int(row[4]), STONE: int(row[5])}, (action, counts)
    print(f"{'Guest' if args.lan else 'Host'} matched six Java Attribute Filter editor states through reference sampling, inversion, mode, save, reopen, and reset.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-afe-") as scratch:
        run(args, Path(scratch))


if __name__ == "__main__":
    main()
