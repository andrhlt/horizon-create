#!/usr/bin/env python3
"""Compare Create’s nine lava and water spouts and their conversion targets."""

import argparse
import csv
import json
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/fluids/spouting.nbt")
SPOUTS = ((6, 99, -11), (6, 99, -9), (7, 99, -9), (8, 99, -9),
          (9, 99, -9), (10, 99, -9), (8, 99, -11), (9, 99, -11), (10, 99, -11))
BLOCKS = ((6, 97, -9), (6, 97, -11), (7, 97, -9), (8, 97, -9), (9, 97, -9), (10, 97, -9))
DEPOTS = ((8, 97, -11), (9, 97, -11), (10, 97, -11))


def command_at(pos):
    return "command " + json.dumps("/data get block " + " ".join(map(str, pos)))


def field(text, key, default="0"):
    match = re.search(rf"\b{key}: (-?\d+)", text)
    return match[1] if match else default


def sample(control, tick):
    actions = [*(command_at(pos) for pos in SPOUTS),
               *("block " + " ".join(map(str, pos)) for pos in BLOCKS),
               *(command_at(pos) for pos in DEPOTS)]
    replies = control.call("script", script="\n".join(actions) + "\n")
    spouts = [item["chat"][-1] for item in replies[:len(SPOUTS)]]
    blocks = [item["state"] for item in replies[len(SPOUTS):-len(DEPOTS)]]
    depots = [item["chat"][-1] for item in replies[-len(DEPOTS):]]
    if any("create:spout" not in reading for reading in spouts):
        raise RuntimeError(f"Cannot read all nine spouts: {spouts}")
    result = [str(tick)]
    for reading in spouts:
        result += [field(reading, "amount"), field(reading, "ProcessingTicks", "-1")]
    moisture = re.search(r"moisture=(\d)", blocks[0])
    result.append(moisture[1] if moisture else "-1")
    result += [state.split("[", 1)[0] for state in blocks[1:]]
    for reading in depots:
        result.append(next((name for name in re.findall(r'\bid: "([^"]+)"', reading)
                            if name != "create:depot"), "-"))
    if tick == 149 and "minecraft:water" not in depots[1]:
        raise RuntimeError(f"The bottle lacks the water potion component: {depots[1]}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    args = parser.parse_args()
    with (ROOT / "fixtures/spouting-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    actual = []
    with fixture_world(args, "Spouting", STRUCTURE) as control:
        control.command("/gamerule random_tick_speed 0")
        control.command("/place template create:gametest/fluids/spouting 3 96 -12")
        control.command("/setblock 5 98 -10 minecraft:lever[face=wall,facing=east,powered=false]")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
    path = ROOT / ".local/spouting-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    mismatches = [(a[0], {name: (left, right)
                          for name, left, right in zip(header, a, b, strict=True) if left != right})
                  for a, b in zip(expected, actual, strict=True) if a != b]
    if mismatches:
        raise SystemExit(f"Spouting differs on {len(mismatches)} ticks. First differences "
                         f"(Java, Horizon): {mismatches[:5]}. See {path}")
    print(f"Original spouting fixture matched all nine lanes across {len(expected)} ticks. See {path}")


if __name__ == "__main__":
    main()
