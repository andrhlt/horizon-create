#!/usr/bin/env python3
"""Replay the original Smart Observer block and chute GameTests."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world


def state_test(chat):
    if "Test passed" in chat:
        return "1"
    if "Test failed" in chat:
        return "0"
    raise RuntimeError(f"Unexpected block test response: {chat}")


def read_timer(chat):
    tag = re.search(r"\bTurnOff: (\d+)", chat)
    if not tag or "create:content_observer" not in chat:
        raise RuntimeError(f"Missing observer timer: {chat}")
    return tag[1]


def test_block(pos, block):
    return f"/execute if block {pos} {block}"


def block_rows(control, tick):
    for column, item in ((1, "gold_ore"), (3, "gold_block")):
        x = 3 + column
        observer = f"{x} 99 -10"
        present, power, timer, light = control.commands((
            test_block(f"{x} 99 -11", f"minecraft:{item}"),
            test_block(observer, "create:content_observer[powered=true]"),
            f"/data get block {observer}",
            test_block(f"{x} 99 -9", "minecraft:redstone_lamp[lit=true]"),
        ))
        yield [str(tick), str(column), state_test(present), state_test(power),
               read_timer(timer), state_test(light)]


def chute_rows(control, tick):
    observer = "4 98 -10"
    bottom, middle, top, power, timer, output = control.commands((
        *(f"/data get block 4 {y} -11" for y in (98, 99, 100)),
        test_block(observer, "create:content_observer[powered=true]"),
        f"/data get block {observer}",
        test_block("4 100 -9", "minecraft:diamond_block"),
    ))
    counts = []
    for tag in (bottom, middle, top):
        if "create:chute" not in tag and "create:smart_chute" not in tag:
            raise RuntimeError(f"Missing chute: {tag}")
        counts.append(str(sum(map(int, re.findall(r"\b(?:count|Count): (\d+)", tag)))))
    yield [str(tick), *counts, state_test(power), read_timer(timer), state_test(output)]


def run(args, variant):
    fixture = f"smart_observer_{variant}"
    blocks = variant == "blocks"
    category = "misc" if blocks else "items"
    structure = f"gametest/{category}/{fixture}"
    reader = block_rows if blocks else chute_rows
    with (ROOT / f"fixtures/{fixture}-java.csv").open() as file:
        rows = csv.reader(file)
        header, expected = next(rows), list(rows)
    actual = []
    with fixture_world(args, fixture, Path(structure + ".nbt")) as control:
        control.command(f"/place template create:{structure} 3 96 -12")
        if blocks:
            lever = "/setblock 5 97 -11 minecraft:lever[face=floor,facing=south,powered={}]"
            control.command(lever.format("true"))
        else:
            control.command("/setblock 4 100 -10 minecraft:lever[face=wall,facing=south,powered=false]")
        start = control.clock()
        for tick in range(len(expected) // (2 if blocks else 1)):
            if tick:
                control.step_to(start + tick)
            actual.extend(reader(control, tick))
            if blocks and tick in (10, 23):
                control.command(lever.format("false" if tick == 10 else "true"))

    path = ROOT / f".local/{fixture}-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"{fixture} differs in {len(differences)} rows. "
                         f"First rows (Java, Horizon): {differences[:5]}")
    print(f"{fixture} matched all Java ticks. See {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--variant", choices=("blocks", "chutes"), action="append")
    args = parser.parse_args()
    for variant in args.variant or ("blocks", "chutes"):
        run(args, variant)


if __name__ == "__main__":
    main()
