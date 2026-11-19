#!/usr/bin/env python3
"""Replay Create's original andesite_tunnel_split GameTest."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/items/andesite_tunnel_split.nbt")
BELT = "4 97 -10"
SUPPLY = "4 101 -10"
CHUTE = "4 100 -10"
DEPOTS = ("5 97 -11", "6 97 -11", "7 97 -10")


def count(items):
    return sum(map(int, re.findall(r"\b(?:count|Count): (\d+)", items)))


def sample(control, tick):
    supply, chute, belt, *depots = control.commands([
        *(f"/data get block {pos} Items" for pos in (SUPPLY, CHUTE)),
        f"/data get block {BELT}",
        *(f"/data get block {pos} Items" for pos in DEPOTS),
    ])
    if "create:belt" not in belt:
        raise RuntimeError(f"Cannot read the tunnel belt controller: {belt}")
    match = re.search(r"\bPos: (-?\d+(?:\.\d+)?)", belt)
    position = float(match[1]) if match else -1.0
    carried = count(belt) if match else 0
    return [str(tick), str(count(supply)), str(count(chute)), str(carried), f"{position:.7f}",
            *(str(count(depot)) for depot in depots)]


def run(args):
    with (ROOT / "fixtures/andesite_tunnel_split-java.csv").open() as file:
        rows = csv.reader(file)
        header, expected = next(rows), list(rows)
    actual = []
    with fixture_world(args, "Tunnel-split", STRUCTURE, render=True) as control:
        control.command("/place template create:gametest/items/andesite_tunnel_split 3 96 -12")
        control.command("/setblock 5 101 -10 minecraft:lever[face=wall,facing=east,powered=false]")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
        control.command("/fill 3 96 -17 8 96 -13 minecraft:smooth_stone")
        control.command("/time set noon")
        control.call("tp", 7.5, 97, -14.7)
        control.call("look-at", 5.5, 97.6, -10.7)
        control.call("key", "f1", "tap")
        control.call("wait", 4)
        control.call("screenshot", ROOT / ".local/andesite_tunnel_split.png")

    path = ROOT / ".local/andesite_tunnel_split-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [
        (a, b) for a, b in zip(expected, actual, strict=True)
        if a[:4] != b[:4] or a[5:] != b[5:] or abs(float(a[4]) - float(b[4])) > 0.000001
    ]
    if differences:
        raise SystemExit(f"Tunnel differs on {len(differences)} ticks. "
                         f"First rows (Java, Horizon): {differences[:5]}. See {path}")
    print(f"Andesite tunnel split matched {len(actual)} Java ticks. See {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())


if __name__ == "__main__":
    main()
