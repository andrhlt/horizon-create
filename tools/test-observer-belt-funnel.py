#!/usr/bin/env python3
"""Replay Create's original belt and funnel Smart Observer GameTest."""

import argparse
import csv
import json
import math
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/items/smart_observer_belt_and_funnel.nbt")
ORIGIN = (3, 96, -12)
OBSERVERS = ((3, 1, 2), (6, 2, 4))
CHESTS = ((7, 2, 3), (1, 2, 3))
OUTPUT = ((5, 1, 1), (2, 3, 6), (6, 1, 1), (1, 2, 6))
GANTRY_SHAFT = (5, 1, 6)
GEARSHIFT = (6, 1, 6)


def xyz(local):
    return tuple(base + step for base, step in zip(ORIGIN, local, strict=True))


def coordinate(local):
    return " ".join(map(str, xyz(local)))


def sample(control, tick):
    queries = [
        *(f"/data get block {coordinate(pos)} TurnOff" for pos in OBSERVERS),
        f"/data get entity @e[type=minecraft:marker,limit=1] Pos[0]",
        *(f"/data get block {coordinate(pos)} Items" for pos in CHESTS),
    ]
    events = [*(f"block {coordinate(pos)}" for pos in (*OBSERVERS, *OUTPUT)),
              *(f"command {json.dumps(q)}" for q in queries)]
    replies = control.call("script", script="\n".join(events) + "\n")
    b_obs, f_obs, *blocks = replies[:6]
    b_time, f_time, pos, supply, dest = (line.get("chat", [""])[-1] for line in replies[6:])
    count = lambda nbt: sum(map(int, re.findall(r"\b(?:Count|count): (\d+)", nbt)))
    timer = lambda nbt: int(re.search(r"(-?\d+)$", nbt)[1])
    match = re.search(r"(-?\d+(?:\.\d+)?)d$", pos)
    relative = float(match[1]) - xyz((5, 2, 6))[0] if match else 999.0
    on = lambda state: int("powered=true" in state["state"])
    values = (tick, on(b_obs), timer(b_time), on(f_obs), timer(f_time), relative,
              *(int(block["block"] == "minecraft:diamond_block") for block in blocks),
              count(supply), count(dest))
    return values


def run(args):
    with (ROOT / "fixtures/smart_observer_belt_and_funnel-java.csv").open() as reference:
        source = csv.reader(reference)
        header = next(source)
        expected = [tuple(map(float, row)) for row in source]
    actual = []
    diagnostics = []
    with fixture_world(args, "Observer-belt-funnel", STRUCTURE, render=args.visual) as control:
        control.command(f"/place template create:{STRUCTURE.with_suffix('')} {' '.join(map(str, ORIGIN))}")
        control.command(f"/setblock {coordinate((6, 2, 2))} minecraft:lever[face=floor,facing=south,powered=false]")
        start = control.clock()
        for row in expected:
            t = int(row[0])
            control.step_to(start + t)
            control.call("wait", 1)
            actual.append(sample(control, t))
            if args.diagnostics and t < 62:
                state = control.commands((
                    f"/data get block {coordinate(GEARSHIFT)}",
                    f"/data get block {coordinate(GANTRY_SHAFT)}",
                ))
                diagnostics.append((t, *state))
        if args.visual:
            control.command("/time set noon")
            control.command("/tp @s 13.5 103 -4 100 25")
            control.call("wait", 4)
            control.call("look-at", 7, 98, -8)
            control.call("key", "f1", "tap")
            control.call("wait", 4)
            control.call("screenshot", ROOT / ".local/smart-observer-belt-funnel.png")
    trace = ROOT / ".local/smart_observer_belt_and_funnel-horizon.csv"
    with trace.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    if diagnostics:
        (ROOT / ".local/gantry-timing.log").write_text(
            "".join(f"{t}\t{gearshift}\t{shaft}\n" for t, gearshift, shaft in diagnostics))
    differences = [(int(java[0]), [(key, exp, got) for key, exp, got in zip(header, java, horizon, strict=True)
                                  if not math.isclose(exp, got, abs_tol=1e-6, rel_tol=0)])
                   for java, horizon in zip(expected, actual, strict=True)]
    differences = [(t, cols) for t, cols in differences if cols]
    if differences:
        raise SystemExit(f"Belt and funnel observers differed on {len(differences)} ticks. "
                         f"First differences: {differences[:6]}. See {trace}")
    print(f"Smart Observers, pistons, and translating gantry matched all {len(actual)} Java ticks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
