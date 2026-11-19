#!/usr/bin/env python3
"""Compare the original potion-fed redstone spout factory."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/spout_crafting.nbt")


def number(text, key, default=0.0):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", text)
    return float(match[1]) if match else default


def sample(control, tick):
    belt, pump, spout, chest = control.commands((
        "/data get block 5 97 -11",
        "/data get block 6 100 -11",
        "/data get block 6 99 -11",
        "/data get block 8 98 -11 Items",
    ))
    if "create:spout" not in spout:
        raise RuntimeError(f"Cannot read original spout: {spout}")
    if "minecraft:strength" not in spout or "create:potion" not in spout:
        raise RuntimeError(f"Spout lost the original strength potion: {spout}")
    redstone = "minecraft:redstone"
    def count(text, identity):
        return sum(int(number(stack, "count")) for stack in re.findall(r"\{[^{}]*\}", text)
                   if f'id: "{identity}"' in stack)

    front = max((float(m) for m in re.findall(r"\bPos: (-?\d+(?:\.\d+)?)", belt)), default=0.0)
    return [str(tick), f'{number(belt, "Speed"):.4f}', f'{number(pump, "Speed"):.4f}',
            str(int(number(spout, "ProcessingTicks", -1))), str(int(number(spout, "amount"))),
            str(count(belt, "create:cinder_flour")), str(count(belt, redstone)), f"{front:.7f}",
            str(count(chest, redstone))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--visual", action="store_true")
    args = parser.parse_args()
    with (ROOT / "fixtures/spout_crafting-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    actual = []
    with fixture_world(args, "Spout-crafting", STRUCTURE, render=args.visual) as control:
        if args.visual:
            control.command("/fill 0 97 -15 13 109 -5 minecraft:air")
            control.command("/fill 3 96 -8 9 96 -5 minecraft:smooth_stone")
        control.command("/place template create:gametest/processing/spout_crafting 3 96 -12")
        control.command("/setblock 5 98 -10 minecraft:lever[face=floor,facing=north,powered=false]")
        if args.visual:
            control.command("/tp @s 7.7 97 -6.0 180 0")
            control.call("look-at", 6.5, 98.6, -10.5)
            control.call("key", "f1", "tap")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
            if args.visual and tick in (47, 57, 64):
                control.call("screenshot", ROOT / f".local/spout-visual-{tick}.png")
    path = ROOT / ".local/spout_crafting-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True)
                   if a[:7] != b[:7] or abs(float(a[7]) - float(b[7])) > 0.000001 or a[8] != b[8]]
    if differences:
        raise SystemExit(f"Spout crafting passes on {len(actual)-len(differences)} of {len(actual)} ticks. "
                         f"First differences (Java, Horizon): {differences[:5]}. See {path}")
    print(f"Original spout crafting matched Java across {len(expected)} ticks. See {path}")


if __name__ == "__main__":
    main()
