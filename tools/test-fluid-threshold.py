#!/usr/bin/env python3
"""Replay the original three-valve fluid Threshold Switch fixture."""

import argparse
import csv
import json
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/fluids/threshold_switch.nbt")
HANDLES = ((7, 97, -8), (5, 97, -8), (6, 98, -10))
ACTIONS = {0: 0, 117: 1, 244: 2}


def number(nbt, key):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?)", nbt)
    return float(match[1]) if match else 0.0


def turns(control, position):
    x, y, z = position
    # Stand on the handle's exposed side. The runner uses the same click as a player.
    control.command(f"/tp @s {x + 0.5} {y} {z + 1.7} 180 20")
    control.call("wait", 3)
    reply = control.call("interact", x, y, z, "south")
    state = control.command(f"/data get block {x} {y} {z} InUse")
    if number(f"InUse: {state.split()[-1]}", "InUse") <= 0:
        raise RuntimeError(f"Click did not turn the valve handle at {position}: {state}, {reply}")


def sample(control, tick):
    tested = (
        ((4, 98, -11), "minecraft:redstone_lamp[lit=true]"),
        *((pos, "create:fluid_valve[enabled=true]") for pos in
          ((7, 97, -9), (5, 97, -9), (6, 98, -11))),
    )
    commands = (
        "/data get block 8 97 -9",
        "/data get block 4 97 -9",
        "/data get block 5 97 -11",
        "/data get block 4 97 -11",
        *(f"/data get block {x} {y} {z}" for x, y, z in HANDLES),
        *(f"/execute if block {x} {y} {z} {state} run say Valve trace active"
          for (x, y, z), state in tested),
    )
    details = control.call("script", script="".join(f"command {json.dumps(cmd)}\n" for cmd in commands))
    left, right, central, sensor, *replies = [(r.get("chat") or [""])[-1] for r in details]
    handles = replies[:3]
    data = [str(tick), *(str(int(number(tank, "amount"))) for tank in (left, right, central)),
            *(str(int(number(sensor, key))) for key in ("CurrentAmount", "Powered", "PoweredAfterDelay"))]
    data.extend(str(int("Valve trace active" in line)) for line in replies[3:])
    for handle in handles:
        data.extend((str(int(number(handle, "InUse") > 0)),
                     str(int(number(handle, "TotalUseTicks"))),
                     f'{number(handle, "Speed"):.4f}'))
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()
    with (ROOT / "fixtures/fluid_threshold-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)[:args.ticks]
    actual = []
    with fixture_world(args, "Fluid-threshold", STRUCTURE) as control:
        control.command("/place template create:gametest/fluids/threshold_switch 3 96 -12")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
            if tick in ACTIONS and tick + 1 < len(expected):
                turns(control, HANDLES[ACTIONS[tick]])
    path = ROOT / ".local/fluid_threshold-horizon.csv"
    with path.open("w", newline="") as file:
        output = csv.writer(file, lineterminator="\n")
        output.writerow(header)
        output.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"Fluid Threshold Switch differs on {len(differences)} ticks. "
                         f"First differences (Java, Horizon): {differences[:4]}. See {path}")
    print(f"Valve and fluid Threshold Switch matched all {len(actual)} Java ticks. See {path}")


if __name__ == "__main__":
    main()
