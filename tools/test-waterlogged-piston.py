#!/usr/bin/env python3
"""Replay the original sticky piston disassembly and retraction through a water source."""

import argparse
import csv
from pathlib import Path

from fixture_world import ROOT, fixture_world

TEMPLATE = Path("gametest/contraptions/ploughing.nbt")
STATES = (
    ("minecraft:air", ("minecraft:air", "absent", "false", "absent", "absent")),
    ("minecraft:water[level=0]", ("minecraft:water", "absent", "true", "absent", "absent")),
    ("create:mechanical_piston_head[waterlogged=true,facing=east,type=sticky]",
     ("create:mechanical_piston_head", "true", "true", "east", "sticky")),
    ("create:mechanical_plough[waterlogged=true,facing=east]",
     ("create:mechanical_plough", "true", "true", "east", "absent")),
)
TARGET = "28 98 -11"


def run(args):
    with (ROOT / "fixtures/waterlogged-piston-java.csv").open() as trace:
        rows = csv.reader(trace)
        next(rows)
        expected = [tuple(row) for row in rows]
    assert len(expected) == 45
    actual = []
    with fixture_world(args, "WaterloggedPiston", TEMPLATE, pack=args.pack) as control:
        control.command("/gamerule random_tick_speed 0")
        while control.clock() % 20 != 2:
            control.step_to(control.clock() + 1)
        control.commands((
            "/place template create:gametest/contraptions/ploughing 25 96 -12",
            "/setblock 28 98 -10 minecraft:lever[face=floor,facing=west,powered=false]",
        ))
        baseline = control.clock()
        for tick in range(1, 46):
            control.step_to(baseline + tick)
            if tick == 4:
                control.command(f"/setblock {TARGET} minecraft:water[level=0]")
            outcomes = control.commands(f"/execute if block {TARGET} {state}" for state, _ in STATES)
            matched = [observed for (_, observed), result in zip(STATES, outcomes, strict=True)
                       if "Test passed" in result]
            if len(matched) != 1:
                block = control.call("block", 28, 98, -11)
                raise RuntimeError(f"Unexpected target state on tick {tick}: {block}")
            actual.append((str(tick), *matched[0]))
            if tick == 24:
                control.command("/data merge block 29 97 -10 {ScrollValue:-64}")
    if actual != expected:
        diffs = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
        raise RuntimeError(f"Piston waterlogging differs: {diffs}")
    print("All 45 Java piston water samples matched tick for tick.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
