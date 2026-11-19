#!/usr/bin/env python3
"""Trace the arm-fed brass production and rotating basin fixture."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/brass_mixing_2.nbt")
COUNT = re.compile(r'\b(?:Count|count): (\d+)')
IDENTITY = re.compile(r'\bid: "([\w:]+)"')


def number(text, key, default=0.0):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", text)
    return float(match[1]) if match else default


def item(text):
    count, identity = COUNT.search(text), IDENTITY.search(text)
    return (identity[1], int(count[1])) if identity and count else ("-", 0)


def sample(control, tick):
    arm, held, zinc, copper, old_zinc, old_copper, mixer, basin, receiver = control.commands((
        "/data get block 5 98 -6",
        "/data get block 5 98 -6 HeldItem",
        "/data get block 7 97 -4 Items",
        "/data get block 4 97 -4 Items",
        "/data get block 7 97 -4 HeldItem",
        "/data get block 4 97 -4 HeldItem",
        "/data get block 6 100 -9",
        "/data get block 6 98 -9 Items",
        "/data get block 4 97 -9 Items",
    ))
    if "create:mechanical_arm" not in arm:
        raise RuntimeError(f"Cannot read the mechanical arm: {arm}")
    phase = re.search(r'\bPhase: "([A-Z_]+)"', arm)
    held_id, held_count = item(held)
    stacks = tuple(item(token) for token in re.findall(r"\{[^{}]*\}", basin))
    return [
        str(tick), f'{number(arm, "Speed"):.4f}', phase[1] if phase else "SEARCH_INPUTS",
        str(int(number(arm, "TargetPointIndex"))), f'{number(arm, "MovementProgress"):.7f}',
        held_id, str(held_count), str(item(zinc)[1] or item(old_zinc)[1]),
        str(item(copper)[1] or item(old_copper)[1]),
        f'{number(mixer, "Speed"):.4f}', str(bool(number(mixer, "Running"))).lower(),
        str(int(number(mixer, "Ticks"))), str(int(number(mixer, "ProcessingTicks"))),
        *(str(sum(count for name, count in stacks if name == wanted))
          for wanted in ("create:zinc_ingot", "minecraft:copper_ingot")),
        str(item(receiver)[1]),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()
    with (ROOT / "fixtures/arm_brass_mixing-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    if args.ticks is not None:
        expected = expected[:args.ticks]
    results = []
    with fixture_world(args, "Arm-brass", STRUCTURE, pack=args.pack) as control:
        control.command("/place template create:gametest/processing/brass_mixing_2 3 96 -12")
        arm_lever = "/setblock 6 98 -7 minecraft:lever[face=floor,facing=west,powered={}]"
        control.command(arm_lever.format("false"))
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            if tick == 140:
                control.command(arm_lever.format("true"))
            if tick == 200:
                control.command("/setblock 6 98 -11 minecraft:lever[face=floor,facing=west,powered=false]")
            results.append(sample(control, tick))
    path = ROOT / ".local/arm_brass_mixing-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(results)
    differences = [(a, b) for a, b in zip(expected, results, strict=True) if a != b]
    if differences:
        raise SystemExit(f"Arm-fed brass diverges on {len(differences)} ticks. First "
                         f"rows (Java, Horizon): {differences[:5]}. See {path}")
    print(f"Arm-fed brass matched Java across {len(expected)} ticks. See {path}")


if __name__ == "__main__":
    main()
