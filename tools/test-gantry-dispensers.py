#!/usr/bin/env python3
"""Replay the Java Create gantry fixtures for mounted dispensers."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

SCENARIOS = {"dispensers_dont_fight": 3, "dispensers_refill": 17}
GANTRY = "@e[type=minecraft:marker,tag=create_gantry_payload,limit=1]"
POSITION = re.compile(r"\[(-?[\d.Ee+-]+)d, (-?[\d.Ee+-]+)d, (-?[\d.Ee+-]+)d\]")


def amount(reply):
    return sum(map(int, re.findall(r"\bcount: (\d+)", reply)))


def sample(control, scenario, base):
    x, y, z = base
    marker = control.command(f"/data get entity {GANTRY} Pos")
    position = POSITION.search(marker)
    if position:
        carriage = ":".join(f"{float(value) - origin:.9f}"
                            for value, origin in zip(position.groups(), base, strict=True))
        payload = f"/data get entity {GANTRY} CreateGantry.Blocks"
        requests = [f'{payload}[{{Pos:[I;0,{dy},0]}}].VanillaEntity.Items' for dy in (1, 3)]
        requests.append(f'{payload}[{{Pos:[I;-1,1,0]}}].VanillaEntity.Items')
        lower, upper, barrel = map(amount, control.commands(requests))
    else:
        carriage = ""
        found = control.commands(f"/data get block {x + dx} {y + dy} {z + 1} Items"
                                 for dx in (3, 5) for dy in (3, 5))
        lower = amount(found[0]) + amount(found[2])
        upper = amount(found[1]) + amount(found[3])
        barrel = 0
        if scenario == "dispensers_refill":
            barrels = control.commands(f"/data get block {x + dx} {y + 3} {z + 1} Items" for dx in (2, 4))
            barrel = sum(map(amount, barrels))
    kind = "spectral_arrow" if scenario == "dispensers_refill" else "arrow"
    arrows = f"@e[type=minecraft:{kind},x={x},y={y},z={z},dx=9,dy=7,dz=3]"
    report = control.call("command", f"/execute as {arrows} run data get entity @s Pos")["chat"]
    heights = [float(match[2]) - y for row in report if (match := POSITION.search(row))]
    low = sum(height < 4.5 for height in heights)
    return [carriage, *map(str, (lower, upper, barrel, low, len(heights) - low))]


def run(args):
    scenario = args.scenario
    base = (SCENARIOS[scenario], 96, -12)
    template = Path(f"gametest/contraptions/{scenario}.nbt")
    with (ROOT / f"fixtures/{scenario}-java.csv").open() as reference:
        rows = csv.reader(reference)
        full_header = next(rows)
        header = full_header[:2] + full_header[3:]
        expected = [row[:2] + row[3:] for row in list(rows)[:args.ticks]]
    actual = []
    with fixture_world(args, scenario, template) as control:
        while control.clock() % 20 != int(expected[0][1]):
            control.step_to(control.clock() + 1)
        x, y, z = base
        control.commands((
            f"/place template create:{template.with_suffix('')} {x} {y} {z}",
            f"/setblock {x+2} {y+2} {z+1} minecraft:lever[face=floor,facing=east,powered=false]",
        ))
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append([str(tick), str((start + tick) % 20), *sample(control, scenario, base)])
    path = ROOT / f".local/{scenario}-horizon.csv"
    with path.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want[0], {key: (a, b) for key, a, b in zip(header, want, got, strict=True) if a != b})
                   for want, got in zip(expected, actual, strict=True) if want != got]
    if differences:
        raise SystemExit(f"{scenario} differed at {len(differences)} ticks. First differences (Java, Horizon) {differences[:6]}.")
    print(f"{scenario} matched all {len(actual)} Java ticks. See {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("scenario", choices=tuple(SCENARIOS))
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()
    if args.ticks is not None and args.ticks < 1:
        parser.error("--ticks must be positive")
    run(args)
