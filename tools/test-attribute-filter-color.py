#!/usr/bin/env python3
"""Compare Create's Attribute Filter color decisions on items and fireworks."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


attribute = import_module("test-attribute-filter-kinds")
filters = attribute.filters


def measured(args, temporary):
    with (ROOT / "fixtures/attribute-filter-color-java.csv").open(newline="") as file:
        rows = list(csv.reader(file))
    assert len(rows) == 42
    with fixture_world(args, "AttributeFilterColor", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 4 100 -14 16 100 -4 minecraft:smooth_stone",
            "/fill 4 101 -14 16 110 -4 minecraft:air",
            "/tp @s 8.5 101 -11.5 0 -80",
        ))
        with filters.actor_for(host, args, temporary if args.lan else None) as (actor, name):
            for index, color, rule, sample, expected in rows:
                nbt = attribute.original_string(sample)
                actual = attribute.apply_case(host, attribute.original_string(rule), nbt)
                assert actual == int(expected == "true"), (index, color, nbt, expected, actual)
            attribute.by_hand(host, actor, name, kind="create:has_color", value='"blue"',
                              sample='{Slot:0b,id:"minecraft:blue_wool",count:1}')
    print(f"{'Guest' if args.lan else 'Host'} matched 42 Java item color results and applied the blue filter by hand.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-afc-") as scratch:
        measured(args, Path(scratch))


if __name__ == "__main__":
    main()
