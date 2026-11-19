#!/usr/bin/env python3
"""Check Create's two visible creative tab memberships against pinned Java."""
import argparse
import csv
from importlib import import_module
import json
from pathlib import Path
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")


def pack_tabs(pack):
    with (ROOT / "fixtures/creative-tabs-java.csv").open() as trace:
        expected = {name: [] for name in ("base", "palettes")}
        for row in csv.DictReader(trace):
            if row["visibility"] == "display":
                expected[row["tab"]].append(row["item"])
    with ZipFile(pack) as archive:
        tabs = {name: json.loads(archive.read(f"data/create/horizon/creative_tab/{name}.json"))
                for name in expected}
    for name, reference in expected.items():
        actual = tabs[name]["items"]
        if len(actual) != len(set(actual)) or set(actual) != set(reference):
            missing, extra = sorted(set(reference) - set(actual)), sorted(set(actual) - set(reference))
            raise AssertionError(f"{name}: missing {missing}; extra {extra}; {len(actual)} rows")
    if tabs["palettes"]["items"] != expected["palettes"]:
        raise AssertionError("Building Blocks display order differs from Java.")
    return tabs


def first_page(world):
    slots = {int(widget["id"][5:]): widget["stack"]["item"]
             for widget in world.call("ui")["widgets"]
             if widget["id"].startswith("slot-") and widget.get("stack")}
    return [slots[index] for index in range(900, 945) if index in slots]


def run(args):
    tabs = pack_tabs(args.pack)
    with fixture_world(args, "Creative tabs display", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        world.call("open-inventory")
        widgets = world.call("ui")["widgets"]
        left, top, *_ = next(widget["bounds"] for widget in widgets if widget["id"] == "slot-900")
        # Creative grid starts at (9, 18). The page button centers are 10 px in.
        x, y = left - 9, top - 18
        world.call("click-at", x + 185, y - 40)
        for column, (name, data) in enumerate(tabs.items()):
            world.call("click-at", x + 13 + column * 27, y - 13)
            multiplayer.until(f"{name} live creative display", lambda: first_page(world) == data["items"][:45])
            print(f"{name}: {len(data['items'])} Java display items and matching first live page.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
