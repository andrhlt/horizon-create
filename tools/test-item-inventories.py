#!/usr/bin/env python3
"""Compare inventory contents in three original Create item GameTests."""
import argparse
from collections import Counter
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

SCENARIOS = {
    "storages": (35, 20, (12, 2, 2), "floor", "north", ((13, 2, 1), (10, 2, 1), (7, 2, 1), (4, 2, 1), (1, 2, 1))),
    "belt_coaster": (21, 0, (1, 4, 5), "wall", "north", ((1, 4, 6), (3, 7, 6))),
    "attribute_filters": (
        3, 0, (2, 2, 1), "floor", "south",
        (*((x, 1, 1) for x in range(3, 11)), (11, 1, 2)),
    ),
}


def world_pos(origin, local):
    return tuple(world + offset for world, offset in zip(origin, local, strict=True))


def location(pos):
    return " ".join(map(str, pos))


def contents(reply):
    if "no elements matching" in reply.lower():
        return ""
    _, separator, data = reply.partition("has the following block data: ")
    if not separator:
        raise RuntimeError(f"Unable to read the fixture inventory: {reply}")
    values = Counter()
    for match in re.finditer(r'count: (\d+).*?\bid: "([\w:/.-]+)"', data):
        values[match[2]] += int(match[1])
    return "|".join(f"{item}={count}" for item, count in sorted(values.items()))


def run(args):
    origin_x, setup_ticks, lever, face, facing, inventories = SCENARIOS[args.scenario]
    origin = (origin_x, 96, -12)
    level = f"gametest/items/{args.scenario}"
    with (ROOT / f"fixtures/{args.scenario}-java.csv").open() as source:
        reader = csv.reader(source)
        header, expected = next(reader), list(reader)[:args.ticks]
    actual = []
    with fixture_world(args, args.scenario, Path(level + ".nbt")) as control:
        control.command(f"/place template create:{level} {location(origin)}")
        start = control.clock()
        for tick in range(1, setup_ticks + 1):
            control.step_to(start + tick)
        lever = world_pos(origin, lever)
        state = f"minecraft:lever[face={face},facing={facing},powered="
        present = control.command(f"/execute if block {location(lever)} {state}true]")
        if present != "Test passed":
            raise RuntimeError(f"Fixture lever is not in its original state: {present}")
        control.command(f"/setblock {location(lever)} {state}false]")
        start = control.clock()
        queries = tuple(f"/data get block {location(world_pos(origin, pos))} Items" for pos in inventories)
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append([str(tick), *(contents(reply) for reply in control.commands(queries))])
    path = ROOT / f".local/{args.scenario}-horizon.csv"
    with path.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want[0], {name: (a, b) for name, a, b in zip(header, want, got, strict=True) if a != b})
                   for want, got in zip(expected, actual, strict=True) if want != got]
    if differences:
        raise SystemExit(f"{args.scenario} differed at {len(differences)} ticks. "
                         f"First differences (Java, Horizon): {differences[:2]}. See {path}")
    print(f"{args.scenario} inventory contents matched all {len(actual)} Java ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()
    if args.ticks is not None and args.ticks < 1:
        parser.error("--ticks must be positive")
    run(args)
