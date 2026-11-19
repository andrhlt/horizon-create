#!/usr/bin/env python3
"""Replay the original Java Create vault-protected furnace minecart fixture."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

SCENARIO = "vaults_protect_fuel"
BASE = (15, 96, -12)
TEMPLATE = Path(f"gametest/contraptions/{SCENARIO}.nbt")
NUMBER = r"(-?[0-9.Ee+\-]+)"
CART = re.compile(rf"\bPos: \[{NUMBER}d, {NUMBER}d, {NUMBER}d\]", re.IGNORECASE)
FUEL = re.compile(r"\bFuel: (\d+)[sS]?\b")


def sample(control):
    x, y, z = BASE
    states = [control.call("block", x + dx, y + dy, z + dz)["state"]
              for dx, dy, dz in ((1, 2, 3), (3, 2, 3), (2, 1, 1))]
    carts = []
    for dx in (1, 3):
        selector = f"@e[type=minecraft:furnace_minecart,x={x+dx},y={y+1},z={z+1},dx=0,dy=1,dz=1,limit=1]"
        entity = control.command(f"/data get entity {selector}")
        pos = CART.search(entity)
        fuel = FUEL.search(entity)
        if pos and fuel:
            carts.append(f"{float(pos[3])-z:.9f}:{fuel[1]}")
        else:
            carts.append("missing")
    analog = []
    responses = control.commands(f"/data get block {x+dx} {y+2} {z+2} OutputSignal" for dx in (1, 3))
    for dx, data in zip((1, 3), responses, strict=True):
        signal = re.search(r": (\d+)$", data)
        block = control.call("block", x+dx, y+2, z+1)["block"]
        analog.extend([signal[1] if signal else "missing", block])
    return [str(f"{key}=true" in state).lower()
            for key, state in zip(("lit", "lit", "powered"), states, strict=True)] + ["|".join(carts), *analog]


def run(args):
    with (ROOT / f"fixtures/{SCENARIO}-java.csv").open() as source:
        reader = csv.reader(source)
        header = next(reader)
        header = header[:2] + header[3:]
        expected = [r[:2] + r[3:] for r in reader]
    actual = []
    with fixture_world(args, SCENARIO, TEMPLATE) as control:
        control.command("/gamerule random_tick_speed 0")
        while control.clock() % 20 != int(expected[0][1]):
            control.step_to(control.clock() + 1)
        x, y, z = BASE
        control.command(f"/place template create:{TEMPLATE.with_suffix('')} {x} {y} {z} none none 1 0 strict")
        # Horizon's template loader does not restore the vanilla comparator's
        # saved output. Both comparators in the unmodified NBT start at 1.
        control.commands(f"/data merge block {x+dx} {y+2} {z+2} {{OutputSignal:1}}" for dx in (1, 3))
        lever = f"{x+2} {y+1} {z+1}"
        control.command(f"/setblock {lever} minecraft:lever[face=floor,facing=south,powered=true]")
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            if tick == 10:
                control.command(f"/setblock {lever} minecraft:lever[face=floor,facing=south,powered=false]")
            actual.append([str(tick), str((start + tick) % 20), *sample(control)])
    output = ROOT / f".local/{SCENARIO}-horizon.csv"
    with output.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(old, new) for old, new in zip(expected, actual, strict=True) if old != new]
    if differences:
        raise SystemExit(f"{SCENARIO} differed on {len(differences)} ticks. First differences (Java, Horizon) {differences[:4]}. See {output}")
    print(f"{SCENARIO} matched all {len(actual)} Java ticks. See {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
