#!/usr/bin/env python3
"""Compare the original Create regression GameTest for efficient deployers."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/regressions/issue9615_efficient_deployers.nbt")
LEVER = "5 100 -12"
DEPLOYERS = ("4 99 -11", "6 99 -11")
GOAL = (4, 98, -8)
STATE = re.compile(r'\bState: "([A-Z]+)"')
TIMER = re.compile(r"\bTimer: (-?\d+)")
RPM = re.compile(r"\bSpeed: (-?[\d.]+)f")


def read_deployers(control):
    data = control.commands(f"/data get block {pos}" for pos in DEPLOYERS)
    row = []
    for x, entity in zip((4, 6), data, strict=True):
        state, timer, speed = STATE.search(entity), TIMER.search(entity), RPM.search(entity)
        if not all((state, timer, speed)):
            raise RuntimeError(f"Missing deployer state at x={x}. {entity}")
        ore = control.call("block", x, 97, -11)["state"].split("[", 1)[0]
        observer = control.call("block", x, 97, -10)["state"]
        powered = re.search(r"\bpowered=(true|false)", observer)
        if not powered:
            raise RuntimeError(f"Unable to read the observer at x={x}. {observer}")
        row.extend((state[1], timer[1], f"{float(speed[1]):.1f}", ore, powered[1]))
    return [*row, control.call("block", *GOAL)["state"].split("[", 1)[0]]


def run(args):
    with (ROOT / "fixtures/issue9615_efficient_deployers-java.csv").open() as source:
        reader = csv.reader(source)
        header, expected = next(reader), list(reader)
    with fixture_world(args, "Efficient-deployers", STRUCTURE) as control:
        time = control.clock()
        for target in range(time + 1, time + (int(expected[0][1]) - time) % 20 + 1):
            control.step_to(target)
        control.command("/place template create:gametest/regressions/issue9615_efficient_deployers 3 96 -12")
        state = f"minecraft:lever[face=wall,facing=north,powered="
        if control.command(f"/execute if block {LEVER} {state}true]") != "Test passed":
            raise RuntimeError("The lever did not begin powered")
        control.command(f"/setblock {LEVER} {state}false]")
        start = control.clock()
        actual = []
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append([str(tick), str((start + tick) % 20), *read_deployers(control)])
    output = ROOT / ".local/issue9615_efficient_deployers-horizon.csv"
    with output.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want[0], {key: (a, b) for key, a, b in zip(header, want, got, strict=True) if a != b})
                   for want, got in zip(expected, actual, strict=True) if want != got]
    if differences:
        raise SystemExit(f"Efficient deployers differed at {len(differences)} ticks. "
                         f"First differences (Java, Horizon) {differences[:3]}. See {output}")
    print(f"Efficient deployers matched all {len(actual)} Java ticks. See {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
