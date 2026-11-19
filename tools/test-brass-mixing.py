#!/usr/bin/env python3
"""Compare the original brass_mixing factory and mechanical mixer head with Java."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/brass_mixing.nbt")
COUNT = re.compile(r'\b(?:Count|count): (\d+)')


def value(text, key, default=0.0):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", text)
    return float(match[1]) if match else default


def stacks(text):
    for stack in re.findall(r"\{[^{}]*\}", text):
        count = COUNT.search(stack)
        identity = re.search(r'\bid: "([\w:]+)"', stack)
        if count and identity:
            yield identity[1], int(count[1])


def sample(control, tick):
    mixer, contents, overflow, chest = control.commands((
        "/data get block 7 100 -11",
        "/data get block 7 98 -11 Items",
        "/data get block 7 98 -11 Overflow",
        "/data get block 10 98 -11 Items",
    ))
    if "create:mechanical_mixer" not in mixer:
        raise RuntimeError(f"Cannot read the original mechanical mixer: {mixer}")
    inventory = tuple(stacks(contents))
    return [
        str(tick), f'{value(mixer, "Speed"):.7f}',
        *(str(int(value(mixer, key))) for key in ("Running", "Ticks", "ProcessingTicks")),
        *(str(sum(count for item, count in inventory if item == wanted))
          for wanted in ("minecraft:copper_ingot", "create:zinc_ingot")),
        str(sum(count for _, count in stacks(overflow)) +
            sum(count for item, count in inventory if item == "create:brass_ingot")),
        str(sum(count for item, count in stacks(chest) if item == "create:brass_ingot")),
        f'{value(mixer, "HeadOffset", 0.4375):.7f}', f'{value(mixer, "HeadRPM"):.7f}',
    ]


def equal(expected, actual):
    return expected[:9] == actual[:9] and all(
        abs(float(left) - float(right)) <= 0.000001
        for left, right in zip(expected[9:], actual[9:], strict=True)
    )


def run(args):
    with (ROOT / "fixtures/brass_mixing-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    actual = []
    with fixture_world(args, "Brass-mixing", STRUCTURE, pack=args.pack) as control:
        control.command("/place template create:gametest/processing/brass_mixing 3 96 -12")
        control.command("/setblock 5 98 -10 minecraft:lever[face=floor,facing=north,powered=false]")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))

    path = ROOT / ".local/brass_mixing-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a,b) for a,b in zip(expected,actual,strict=True) if not equal(a,b)]
    if differences:
        raise SystemExit(f"Brass mixing differs on {len(differences)} ticks. "
                         f"First rows (Java, Horizon): {differences[:8]}. See {path}")
    print(f"Original brass mixing matched Java across {len(actual)} ticks. See {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
