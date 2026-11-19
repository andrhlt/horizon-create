#!/usr/bin/env python3
"""Replay the original Mechanical Plough GameTest."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

TEMPLATE = Path("gametest/contraptions/ploughing.nbt")
ORIGIN = (25, 96, -12)
POS = re.compile(r"\[(-?[\d.]+)d, (-?[\d.]+)d, (-?[\d.]+)d\]")


def sample(control, tick):
    marker = control.command("/data get entity @e[type=minecraft:marker,tag=create_piston_payload,limit=1] Pos")
    match = POS.search(marker)
    position = ""
    if match:
        relative = (f"{float(value) - base:.9f}" for value, base in zip(match.groups(), ORIGIN))
        position = ":".join((*relative, "0.000000"))
    kinds = ("minecraft:dirt", "minecraft:farmland")
    soil = next((kind for kind, result in zip(kinds, control.commands(
        f"/execute if block 29 97 -11 {kind}" for kind in kinds
    ), strict=True) if "Test passed" in result), "unexpected")
    return [str(tick), str(control.clock() % 20), position, soil]


def check_blocks(control, expected):
    results = control.commands(f"/execute if block {x} 98 -11 {block}" for x, block in expected)
    for (x, block), result in zip(expected, results, strict=True):
        if "Test passed" not in result:
            raise RuntimeError(f"Expected {block} at ({x}, 98, -11). {result}")


def run(args):
    with (ROOT / "fixtures/ploughing-java.csv").open() as reference:
        rows = csv.reader(reference)
        header = next(rows)
        expected = [row[:2] + row[3:] for row in rows]
    with fixture_world(args, "ploughing", TEMPLATE) as control:
        control.command("/gamerule random_tick_speed 0")
        while control.clock() % 20 != int(expected[0][1]):
            control.step_to(control.clock() + 1)
        control.commands((
            "/place template create:gametest/contraptions/ploughing 25 96 -12",
            "/setblock 28 98 -10 minecraft:lever[face=floor,facing=west,powered=false]",
        ))
        start = control.clock()
        actual = []
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
        if actual == expected:
            # The original fixture uses "place when returned". The extra
            # Horizon-only extension/retraction checks below exercise mode 0.
            control.command("/data merge block 27 98 -11 {ScrollValue:0}")
            for tick in range(len(expected), 10):
                control.step_to(start + tick)
            check_blocks(control, ((28, "create:mechanical_piston_head"), (29, "create:mechanical_plough")))
            control.command("/data merge block 29 97 -10 {ScrollValue:-64}")
            for tick in range(10, 23):
                control.step_to(start + tick)
            check_blocks(control, ((26, "create:piston_extension_pole"),
                                   (28, "create:mechanical_plough"), (29, "minecraft:air")))
    with (ROOT / ".local/ploughing-horizon.csv").open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header[:2] + header[3:])
        writer.writerows(actual)
    if actual != expected:
        diffs = [(want, got) for want, got in zip(expected, actual) if want != got]
        raise SystemExit(f"Ploughing differed (Java, Horizon): {diffs}")
    print(f"Ploughing matched all {len(actual)} Java ticks. Full extension and sticky retraction passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
