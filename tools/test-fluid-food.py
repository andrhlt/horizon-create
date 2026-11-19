#!/usr/bin/env python3
"""Replay Java's heated Basin recipes and a Spout's original blaze-cake recipe."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

INGREDIENTS = ("minecraft:honey_block", "create:bar_of_chocolate", "minecraft:cocoa_beans")
SPOUT = "8 106 -11"
DEPOT = "8 104 -11"


def number(tag, key, default=0):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", tag)
    return float(match[1]) if match else default


def count(tag, item):
    return sum(
        int(number(stack, "count")) for stack in re.findall(r"\{[^{}]*\}", tag)
        if f'id: "{item}"' in stack
    )


def quantity(tag, key):
    tanks = re.search(rf"\b{key}: \[([^\]]*)\]", tag)
    return int(number(tanks[1], "amount")) if tanks else 0


def place_setup(control):
    for rig in range(len(INGREDIENTS)):
        z = -11 + rig * 3
        control.command(f"/setblock 4 105 {z} create:creative_motor[facing=up]")
        control.command(f"/data merge block 4 105 {z} {{ScrollValue:256}}")
        control.command(f"/setblock 4 106 {z} create:cogwheel[axis=y]")
        control.command(f"/setblock 5 106 {z} create:mechanical_mixer")
        control.command(f"/setblock 5 104 {z} create:basin")
        control.command(f"/setblock 5 103 {z} create:blaze_burner[blaze=smouldering]")
    control.command(f"/setblock {SPOUT} create:spout")
    control.command(f"/setblock {DEPOT} create:depot")
    control.command(
        f'/data merge block {SPOUT} '
        '{Tanks:[{TankContent:{Fluid:{id:"minecraft:lava",amount:500}}}]}'
    )


def start_processing(control):
    for rig, item in enumerate(INGREDIENTS):
        z = -11 + rig * 3
        control.command(f"/setblock 5 103 {z} create:blaze_burner[blaze=kindled]")
        control.command(f"/data merge block 5 103 {z} {{fuelLevel:1,burnTimeRemaining:1600}}")
        basin = f"5 104 {z}"
        if rig == 2:
            control.command(
                f'/data merge block {basin} '
                '{InputTanks:[{TankContent:{Fluid:{id:"minecraft:milk",amount:500}}},{}]}'
            )
        control.command(f"/item replace block {basin} container.0 with {item} {1 if rig == 0 else 2}")
        if rig == 2:
            control.command(f"/item replace block {basin} container.1 with minecraft:sugar 2")
    control.command(f"/item replace block {DEPOT} container.0 with create:blaze_cake_base")


def sample(control, tick):
    queries = tuple(
        command
        for index in range(len(INGREDIENTS))
        for command in (
            f"/data get block 5 106 {-11 + index * 3}",
            f"/data get block 5 104 {-11 + index * 3}",
        )
    )
    replies = iter(control.commands((*queries, f"/data get block {SPOUT}", f"/data get block {DEPOT} Items")))
    heated = []
    for index, ingredient in enumerate(INGREDIENTS):
        mixer, basin = next(replies), next(replies)
        if "create:mechanical_mixer" not in mixer or "create:basin" not in basin:
            raise RuntimeError(f"Missing mixer or basin: {mixer}, {basin}")
        output = quantity(basin, "OutputTanks")
        identity = ("create:honey", "create:chocolate", "create:chocolate")[index]
        if output and f'id: "{identity}"' not in basin:
            raise RuntimeError(f"Expected the fluid output to be {identity}: {basin}")
        heated.append([
            str(tick), str(index),
            *(str(int(number(mixer, key))) for key in ("Speed", "Running", "Ticks", "ProcessingTicks")),
            str(count(basin, ingredient)), str(quantity(basin, "InputTanks")), str(output),
            f'{number(mixer, "HeadOffset", 0.4375):.7f}', f'{number(mixer, "HeadRPM"):.7f}',
        ])
    spout, depot = next(replies), next(replies)
    cake = [
        str(tick), str(int(number(spout, "ProcessingTicks", -1))), str(quantity(spout, "Tanks")),
        str(count(depot, "create:blaze_cake_base")), str(count(depot, "create:blaze_cake")),
    ]
    return heated, cake


def compare(fixture, actual, tolerance_columns=0):
    with (ROOT / f"fixtures/{fixture}-java.csv").open() as source:
        reader = csv.reader(source)
        headers, expected = next(reader), list(reader)
    trace = ROOT / f".local/{fixture}-horizon.csv"
    with trace.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(actual)
    exact_columns = len(headers) - tolerance_columns
    differences = [
        (java, horizon) for java, horizon in zip(expected, actual, strict=True)
        if java[:exact_columns] != horizon[:exact_columns]
        or any(abs(float(a) - float(b)) > 0.000002 for a, b in zip(
            java[exact_columns:], horizon[exact_columns:], strict=True
        ))
    ]
    if differences:
        print(f"{fixture} differed on {len(differences)} rows (Java, Horizon): {differences[:6]}. See {trace}")
        return False
    print(f"{fixture} matched {len(actual)} Java samples. See {trace}")
    return True


def run(args):
    heated, cake = [], []
    with fixture_world(args, "Fluid-food", pack=args.pack) as control:
        place_setup(control)
        start = control.clock()
        for tick in range(1, 87):
            control.step_to(start + tick)
            mixers, spout = sample(control, tick)
            heated.extend(mixers)
            cake.append(spout)
            if tick == 4:
                start_processing(control)
    cake_passed = compare("blaze-cake-spout", cake)
    mixing_passed = compare("heated-fluids", heated, tolerance_columns=2)
    if not (cake_passed and mixing_passed):
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())


if __name__ == "__main__":
    main()
