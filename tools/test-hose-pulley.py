#!/usr/bin/env python3
"""Compare both Hose Pulley buffers and the full liquid volumes every tick."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/fluids/hose_pulley_transfer.nbt")
REGIONS = tuple(
    tuple((x, y, z) for z in range(-10, -7) for y in range(98, 101)
          for x in range(start, start + 3))
    for start in (5, 11)
)
BLOCK_QUERIES = "".join(
    "blocks " + " ".join(map(str, region[0] + region[-1])) + "\n"
    for region in REGIONS
)


def value(nbt, name):
    match = re.search(rf'\b{name}: (-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)', nbt)
    return float(match[1]) if match else 0.0


def water(state):
    if not state.startswith("minecraft:water"):
        return "-"
    level = re.search(r"level=(\d+)", state)
    level = int(level[1]) if level else 0
    return str(8 if level == 0 or level >= 8 else 8 - level)


def sample(control, tick):
    fill, drain, pump = control.commands((
        "/data get block 7 102 -9",
        "/data get block 11 102 -9",
        "/data get block 9 102 -9",
    ))
    regions = control.call("script", script=BLOCK_QUERIES)
    cells = []
    for region, reply in zip(REGIONS, regions, strict=True):
        by_position = {(x, y, z): state for x, y, z, state in reply["blocks"]}
        cells.append("".join(water(by_position.get(pos, "minecraft:air")) for pos in region))
    return [
        str(tick), f"{value(fill, 'Value'):.4f}", f"{value(drain, 'Value'):.4f}",
        *(f"{value(part, 'Speed'):.4f}" for part in (fill, drain, pump)),
        str(int(value(fill, "amount"))), str(int(value(drain, "amount"))),
        *cells,
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()

    with (ROOT / "fixtures/hose_pulley_transfer-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)[:args.ticks]
    actual = []
    with fixture_world(args, "Hose-pulley", STRUCTURE) as control:
        control.command("/place template create:gametest/fluids/hose_pulley_transfer 3 96 -12 none none 1 0 strict")
        control.command("/setblock 10 102 -7 minecraft:lever[face=wall,facing=south,powered=false]")
        control.call("wait", 3)
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            control.call("wait", 1)
            actual.append(sample(control, tick))
    output = ROOT / ".local/hose_pulley_transfer-horizon.csv"
    with output.open("w") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(left[0], {key: (a, b) for key, a, b in zip(header, left, right, strict=True)
                              if a != b})
                   for left, right in zip(expected, actual, strict=True) if left != right]
    if differences:
        raise SystemExit(f"Hose Pulley transfer differs on {len(differences)} ticks. "
                         f"First differences (Java, Horizon): {differences[:8]}. See {output}")
    print(f"Original Hose Pulley transfer matched all {len(expected)} Java ticks. See {output}")


if __name__ == "__main__":
    main()
