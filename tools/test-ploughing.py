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
            active_before_reload = sample(control, len(expected) - 1)[2:]
            control.restart()
            active_after_reload = sample(control, len(expected) - 1)[2:]
            if active_after_reload[1] != active_before_reload[1] or not active_after_reload[0]:
                raise RuntimeError(f"Active plough state was not retained across save/reopen: {active_before_reload} -> {active_after_reload}")
            # Restart advances the server clock while the client reconnects;
            # align the legacy extension loop's tick-10 origin to that clock.
            start = control.clock() - len(expected) + 1
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
            control.restart()
            check_blocks(control, ((26, "create:piston_extension_pole"),
                                   (28, "create:mechanical_plough"), (29, "minecraft:air")))
    with (ROOT / ".local/ploughing-horizon.csv").open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header[:2] + header[3:])
        writer.writerows(actual)
    if actual != expected:
        diffs = [(want, got) for want, got in zip(expected, actual) if want != got]
        raise SystemExit(f"Ploughing differed (Java, Horizon): {diffs}")
    check_invalid_soil(args, expected[0][1])
    print(f"Ploughing matched all {len(actual)} Java ticks. Full extension, sticky retraction, and invalid-soil boundary passed.")


def check_invalid_soil(args, first_world_time):
    with fixture_world(args, "ploughing_invalid_soil", TEMPLATE) as control:
        control.command("/gamerule random_tick_speed 0")
        while control.clock() % 20 != int(first_world_time):
            control.step_to(control.clock() + 1)
        control.commands((
            "/place template create:gametest/contraptions/ploughing 25 96 -12",
            "/setblock 28 98 -10 minecraft:lever[face=floor,facing=west,powered=false]",
            "/setblock 29 97 -11 minecraft:stone",
        ))
        start = control.clock()
        for tick in range(1, 9):
            control.step_to(start + tick)
        trace = sample(control, 8)
        if not trace[2]:
            raise RuntimeError("Invalid-soil fixture never assembled a moving plough")
        result = control.command("/execute if block 29 97 -11 minecraft:stone")
        if "Test passed" not in result:
            raise RuntimeError(f"Plough changed invalid stone soil: {result}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
