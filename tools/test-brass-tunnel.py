#!/usr/bin/env python3
"""Replay an original Brass Tunnel GameTest with a per-tick count comparison."""

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

ORIGIN = (3, 96, -12)
ROWS = (1, 2, 3)
FILTERING = ((3, 1, 2), (4, 1, 3), (4, 1, 4), (4, 1, 5), (3, 1, 6))


def lanes(x, y, rows=ROWS):
    return tuple((x, y, z) for z in rows)


@dataclass(frozen=True)
class Fixture:
    lever: tuple
    mode: int
    supply: tuple
    tunnels: tuple
    outputs: tuple


SUPPLY = ((1, 2, 3),)
TUNNELS = lanes(3, 2)
FIXTURES = {
    "filtering": Fixture((2, 2, 2), 0, SUPPLY, lanes(3, 2, (3, 4, 5)), FILTERING),
    "prefer_nearest": Fixture((2, 2, 2), 4, SUPPLY, TUNNELS, lanes(5, 1)),
    "round_robin": Fixture((2, 2, 2), 2, SUPPLY, TUNNELS, lanes(7, 2)),
    "split": Fixture((2, 2, 2), 0, SUPPLY, TUNNELS, lanes(7, 1)),
    "sync_input": Fixture((1, 2, 2), 6, lanes(2, 2), lanes(5, 2), lanes(7, 1)),
}


def xyz(local):
    return " ".join(str(origin + offset) for origin, offset in zip(ORIGIN, local, strict=True))


def count(nbt):
    return sum(map(int, re.findall(r"\b(?:count|Count): (\d+)", nbt)))


def run(args):
    key = f"brass_tunnel_{args.mode}"
    fixture = FIXTURES[args.mode]
    structure = Path(f"gametest/items/{key}.nbt")
    with (ROOT / f"fixtures/{key}-java.csv").open() as source:
        rows = csv.reader(source)
        header, expected = next(rows), list(rows)
    actual = []
    with fixture_world(args, key, structure, render=args.visual) as control:
        control.command(f"/place template create:gametest/items/{key} {' '.join(map(str, ORIGIN))}")
        for tunnel in fixture.tunnels:
            control.command(f"/data merge block {xyz(tunnel)} {{ScrollValue:{fixture.mode},StackToDistribute:{{}}}}")
        control.command(f"/setblock {xyz(fixture.lever)} minecraft:lever[face=floor,facing=south,powered=false]")
        start = control.clock()
        fields = [(pos, "Items") for pos in fixture.supply]
        fields += [(pos, "StackToDistribute") for pos in fixture.tunnels]
        fields += [(pos, "Items") for pos in fixture.outputs]
        for row in expected:
            tick = int(row[0])
            if args.mode == "sync_input" and tick in (1, 61, 121):
                z = 1 + (tick - 1) // 60
                control.command(f"/setblock {xyz((3, 3, z))} minecraft:air")
            control.step_to(start + tick)
            samples = control.commands(f"/data get block {xyz(pos)} {field}" for pos, field in fields)
            actual.append((tick, *map(count, samples)))
        if args.visual:
            control.command("/time set noon")
            control.command(f"/tp @s {ORIGIN[0]+8.5} {ORIGIN[1]+8} {ORIGIN[2]+4.5} 90 40")
            control.call("wait", 4)
            control.call("look-at", ORIGIN[0]+3.5, ORIGIN[1]+1.5, ORIGIN[2]+3.5)
            control.call("key", "f1", "tap")
            control.call("wait", 4)
            control.call("screenshot", ROOT / f".local/{key}.png")
    output = ROOT / f".local/{key}-horizon.csv"
    with output.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(tuple(map(int, java)), horizon) for java, horizon in zip(expected, actual, strict=True)
                   if tuple(map(int, java)) != horizon]
    if differences:
        raise SystemExit(f"{args.mode} differed on {len(differences)} of {len(expected)} ticks. "
                         f"First differences (Java, Horizon): {differences[:5]}. See {output}")
    print(f"{args.mode} matched all {len(expected)} Java ticks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--mode", required=True, choices=FIXTURES)
    parser.add_argument("--visual", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
