#!/usr/bin/env python3
"""Compare Create's original held List Filter ghost menu using real player input."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from shutil import which
import struct
from subprocess import check_output
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


package = import_module("test-package-filter-editor")
filters = package.filters
ITEM = "create:filter"
STONE = "minecraft:stone"
PLANKS = "minecraft:oak_planks"
ENTRIES = "create:filter_items"
BLACKLIST = "create:filter_items_blacklist"
RESPECT = "create:filter_items_respect_nbt"


def point(panel, xy):
    return tuple(a + b for a, b in zip(panel, xy, strict=True))


def dimensions(image):
    with image.open("rb") as data:
        return struct.unpack(">II", data.read(24)[16:24])


def scope(actor, image):
    actor.call("screenshot", image)
    width, height = dimensions(image)
    return ((width / 2 - 214) // 2 - 11, (height / 2 - 211) // 2 + 5)


def hotbar(inventory, index):
    return next((int(stack.get("count", 0)) for stack in inventory["hotbar"] if stack["slot"] == index), 0)


def component_state(host, name):
    raw = host.command(f"/data get entity {name} SelectedItem")
    data = package.parsing(raw.split("entity data: ", 1)[1])
    assert data["id"] == ITEM, data
    return data.get("components", {})


def click(actor, panel, xy, *, shift=False):
    if shift:
        actor.call("key", "shift", "down")
    try:
        actor.call("click-at", *point(panel, xy))
    finally:
        if shift:
            actor.call("key", "shift", "up")


def open_editor(actor):
    actor.call("mouse", "right", "click")
    filters.editor.wait_for(actor, "the original List Filter screen", lambda:
        actor.call("state")["screen"] == "mod"
    )


def crop(ffmpeg, image, panel):
    left, top = point(panel, (23, 25))
    return check_output((ffmpeg, "-v", "error", "-i", str(image), "-vf",
                         f"crop=68:32:{left*2:.0f}:{top*2:.0f}",
                         "-pix_fmt", "rgb24", "-f", "rawvideo", "-"))


def ghost_changed(image, baseline, column):
    start = column * 36 * 3
    count = 0
    for row in range(4, 28):
        offset = row * 68 * 3 + start
        count += sum(abs(a - b) > 12 for a, b in zip(
            image[offset+12:offset+84], baseline[offset+12:offset+84], strict=True
        ))
    return count > 45


def reader(host, actor, name, panel, image, ffmpeg, baseline, expected):
    action, slots, ghost0, ghost1, item, stone, planks, held, valid, has_data, black, respect = expected
    assert slots == "18" and valid == "true"
    actor.call("scroll-at", *point(panel, (190, 102)), 0)
    actor.call("wait", 5)
    inventory = actor.call("inventory")
    assert (hotbar(inventory, 0), hotbar(inventory, 1), hotbar(inventory, 2)) == tuple(map(int, (item, stone, planks))), (action, inventory)
    assert int((inventory.get("carried") or {}).get("count", 0)) == int(held), (action, inventory)
    state = component_state(host, name)
    assert (ENTRIES in state) is (has_data == "true"), (action, state)
    def flag(key):
        return None if key not in state else bool(state[key])

    def expected_flag(value):
        return None if value == "null" else value == "true"

    assert (flag(BLACKLIST), flag(RESPECT)) == (expected_flag(black), expected_flag(respect)), (action, state)
    if actor.call("state")["screen"] == "mod":
        actor.call("screenshot", image)
        actual_image = crop(ffmpeg, image, panel)
        actual = [ghost_changed(actual_image, baseline, col) for col in range(2)]
        assert actual == [ghost0 == "1", ghost1 == "1"], (action, actual)
    else:
        actual_entries = {int(entry["slot"]): entry["item"] for entry in state.get(ENTRIES, [])}
        actual_counts = [actual_entries.get(col, {}).get("count", 0) for col in range(2)]
        assert actual_counts == [int(ghost0), int(ghost1)], (action, actual_entries)
        if action == "save":
            assert actual_entries[0]["id"] == STONE, actual_entries


def run(args, scratch):
    expected = list(csv.reader((ROOT / "fixtures/list-filter-editor-java.csv").open(newline="")))
    assert len(expected) == 9
    image = scratch / "list-filter.png"
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to check rendered ghost slots.")
    with fixture_world(args, "ListFilterEditor", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 5 100 -14 16 100 -4 minecraft:smooth_stone",
            "/fill 5 101 -14 16 109 -4 minecraft:air",
        ))
        with filters.actor_for(host, args, scratch if args.lan else None) as (actor, name):
            host.commands((
                f"/tp {name} 8.5 101 -9.5 0 -80",
                f"/gamemode survival {name}",
                f"/item replace entity {name} hotbar.0 with {ITEM}",
                f"/item replace entity {name} hotbar.1 with {STONE} 5",
                f"/item replace entity {name} hotbar.2 with {PLANKS} 4",
            ))
            filters.editor.wait_for(actor, "the holder and both sample stacks", lambda:
                actor.call("inventory")["counts"] == {ITEM: 1, STONE: 5, PLANKS: 4}
            )
            actor.call("select", ITEM)
            actor.call("options-set", "guiScale", "2")
            open_editor(actor)
            panel = scope(actor, image)
            actor.call("scroll-at", *point(panel, (190, 102)), 0)
            actor.call("screenshot", image)
            baseline = crop(ffmpeg, image, panel)

            for row in expected:
                action = row[0]
                if action in ("copy", "duplicate"):
                    click(actor, panel, (63, 186), shift=True)
                elif action == "cursor_copy":
                    click(actor, panel, (82, 186))
                    filters.editor.wait_for(actor, "the Planks stack being carried", lambda:
                        (actor.call("inventory").get("carried") or {}).get("item") == PLANKS
                    )
                    click(actor, panel, (49, 32))
                elif action == "holder":
                    click(actor, panel, (44, 186))
                elif action == "clear_second":
                    click(actor, panel, (82, 186))
                    filters.editor.wait_for(actor, "the cursor to be empty again", lambda:
                        not actor.call("inventory").get("carried")
                    )
                    click(actor, panel, (49, 32))
                elif action == "save":
                    click(actor, panel, (27, 84))
                    click(actor, panel, (68, 84))
                    click(actor, panel, (190, 84))
                    filters.editor.wait_for(actor, "Confirm to close the List Filter", lambda:
                        actor.call("state")["screen"] == "playing"
                    )
                    filters.editor.wait_for(host, "options and samples to commit", lambda:
                        RESPECT in component_state(host, name)
                    )
                elif action == "reopen":
                    open_editor(actor)
                elif action == "reset":
                    click(actor, panel, (30, 32))
                    click(actor, panel, (45, 84))
                    click(actor, panel, (86, 84))
                    click(actor, panel, (190, 84))
                    filters.editor.wait_for(host, "the ghost and options to clear", lambda:
                        ENTRIES not in component_state(host, name)
                    )
                reader(host, actor, name, panel, image, ffmpeg, baseline, row)
    print(f"{'Guest' if args.lan else 'Host'} matched nine original List Filter menu states with rendered ghost slots and actual cursor inventory.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-lfe-") as scratch:
        run(args, Path(scratch))


if __name__ == "__main__":
    main()
