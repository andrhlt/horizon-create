#!/usr/bin/env python3
"""Watch an item cross the original chute and trip Create's Smart Observer."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/items/smart_observer_chutes.nbt")


def number(snbt, name, default=0):
    match = re.search(rf'\b{name}: (-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)', snbt)
    return float(match[1]) if match else default


def sample(control, tick):
    nbt = control.commands((
        "/data get block 4 98 -10",
        "/data get block 4 100 -11",
        "/data get block 4 99 -11",
        "/data get block 4 98 -11",
    ))
    observer, piston, output = control.call(
        "script", script="block 4 98 -10\nblock 4 98 -9\nblock 4 100 -9\n"
    )
    blocks = {
        "minecraft:air": "block.minecraft.air",
        "minecraft:moving_piston": "block.minecraft.moving_piston",
        "minecraft:diamond_block": "block.minecraft.diamond_block",
    }
    row = [str(tick), str(int(number(nbt[0], "TurnOff"))),
           str(int("powered=true" in observer["state"]))]
    for chute in nbt[1:]:
        row.extend((str(int(number(chute, "count"))), f'{number(chute, "ItemPosition", 1):.6f}'))
    row.extend((str(int("extended=true" in piston["state"])), blocks.get(output["block"], output["block"])))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    with (ROOT / "fixtures/smart_observer_chute_motion-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    actual = []
    with fixture_world(args, "Chute-observer", STRUCTURE) as control:
        control.command("/place template create:gametest/items/smart_observer_chutes 3 96 -12")
        control.command("/setblock 4 100 -10 minecraft:lever[face=wall,facing=south,powered=false]")
        control.call("wait", 3)
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
                control.call("wait", 1)
            actual.append(sample(control, tick))

    output = ROOT / ".local/smart_observer_chute_motion-horizon.csv"
    with output.open("w") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a[0], {k: (x, y) for k, x, y in zip(header, a, b, strict=True) if x != y})
                   for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"Smart Observer chutes differs on {len(differences)} ticks. "
                         f"First differences (Java, Horizon): {differences[:8]}. See {output}")
    print(f"Original Smart Observer chutes matched all {len(expected)} Java ticks. See {output}")


if __name__ == "__main__":
    main()
