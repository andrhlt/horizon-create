#!/usr/bin/env python3
"""Replay the Java press-and-basin trace for ice, iron block, andesite and honey block."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

RIGS = (
    ("minecraft:snow_block", "minecraft:ice", 18),
    ("minecraft:iron_ingot", "minecraft:iron_block", 18),
    ("minecraft:flint", "minecraft:andesite", 4),
    ("minecraft:honey_bottle", "minecraft:honey_block", 8),
)


def scalar(nbt, key):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", nbt)
    return int(float(match[1])) if match else 0


def count(nbt, item):
    return sum(
        scalar(stack, "count") for stack in re.findall(r"\{[^{}]*\}", nbt)
        if f'id: "{item}"' in stack
    )


def sample(control, tick):
    replies = iter(control.commands(tuple(
        command
        for index in range(len(RIGS))
        for command in (
            f"/data get block 5 106 {-11 + index * 3}",
            f"/data get block 5 104 {-11 + index * 3} Items",
            f"/data get block 5 104 {-11 + index * 3} InputTanks",
        )
    )))
    for index, (ingredient, result, _) in enumerate(RIGS):
        press, items, tanks = next(replies), next(replies), next(replies)
        if "create:mechanical_press" not in press:
            raise RuntimeError(f"Cannot inspect the compacting press: {press}")
        running = scalar(press, "Running")
        current = scalar(press, "Ticks")
        previous = scalar(press, "PrevTicks")
        curve = (previous / 120) ** 3 if current < 160 else (240 - previous) / 80
        head = min(1, max(0, curve)) * 22 / 16 if running else 0
        yield [
            str(tick), str(index),
            *(str(scalar(press, key)) for key in ("Speed", "Running", "Finished", "Mode", "Ticks")),
            str(count(items, ingredient)), str(count(items, result)), f"{head:.6f}",
            str(scalar(tanks, "amount")), str(count(items, "minecraft:glass_bottle")),
        ]


def load_rigs(control):
    for index, (item, _, amount) in enumerate(RIGS):
        basin = f"5 104 {-11 + index * 3}"
        if index == 2:
            # Load the tank snapshot before the live inventory updates.
            control.command(
                f'/data merge block {basin} '
                '{InputTanks:[{TankContent:{Fluid:{id:"minecraft:lava",amount:200}}},{}]}'
            )
            control.command(f"/item replace block {basin} container.1 with minecraft:gravel 2")
        control.command(f"/item replace block {basin} container.0 with {item} {amount}")


def run(args):
    with (ROOT / "fixtures/basin_compacting-java.csv").open() as source:
        reader = csv.reader(source)
        headers, expected = next(reader), list(reader)
    actual = []
    with fixture_world(args, "Basin-compacting", pack=args.pack) as control:
        for index in range(len(RIGS)):
            z = -11 + index * 3
            control.command(f"/setblock 4 106 {z} create:creative_motor[facing=east]")
            control.command(f"/data merge block 4 106 {z} {{ScrollValue:256}}")
            control.command(f"/setblock 5 106 {z} create:mechanical_press[facing=east]")
            control.command(f"/setblock 5 104 {z} create:basin")
        start = control.clock()
        for tick in range(1, int(expected[-1][0]) + 1):
            control.step_to(start + tick)
            actual.extend(sample(control, tick))
            if tick == 4:
                load_rigs(control)

    output = ROOT / ".local/basin_compacting-horizon.csv"
    with output.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(actual)
    mismatches = [
        (java, horizon)
        for java, horizon in zip(expected, actual, strict=True)
        if (java[:9] != horizon[:9] or java[10:] != horizon[10:]
            or abs(float(java[9]) - float(horizon[9])) > 0.000002)
    ]
    if mismatches:
        raise SystemExit(f"Compacting differed on {len(mismatches)} rows (Java, Horizon): "
                         f"{mismatches[:5]}. See {output}")
    print(f"Four compacting rigs matched {len(actual)} Java samples. See {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())


if __name__ == "__main__":
    main()
