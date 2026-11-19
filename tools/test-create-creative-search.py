#!/usr/bin/env python3
"""Check Java Create search membership and representative live search results."""
import argparse
import csv
import json
from pathlib import Path
from zipfile import ZipFile

from fixture_world import ROOT, fixture_world


def run(args):
    with (ROOT / "fixtures/creative-tabs-java.csv").open() as f:
        rows = list(csv.DictReader(f))
    with ZipFile(args.pack) as pack:
        for tab in ("base", "palettes"):
            data = json.loads(pack.read(f"data/create/horizon/creative_tab/{tab}.json"))
            expected = [r["item"] for r in rows if r["tab"] == tab and r["visibility"] == "search"]
            if data.get("search_items") != expected:
                raise AssertionError(f"{tab} search membership differs from Java")
    with fixture_world(args, "Creative search membership", render=True, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as world:
        for query, item, expected in (
            ("blaze cake base", "create:blaze_cake_base", True),
            ("chromatic compound", "create:chromatic_compound", False),
        ):
            world.call("open-inventory")
            widgets = world.call("ui")["widgets"]
            left, top, *_ = next(w["bounds"] for w in widgets if w["id"] == "slot-900")
            world.call("click-at", left + 172, top - 30)
            world.call("type", query)
            world.call("wait", 5)
            items = {w["stack"]["item"] for w in world.call("ui")["widgets"] if w.get("stack")}
            if (item in items) != expected:
                raise AssertionError(f"{query!r}: expected {item} presence {expected}, found {items}")
            world.call("close")
    print("Java search membership and search-only/excluded items match.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())
