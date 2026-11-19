#!/usr/bin/env python3
"""Compare the original open-pipe ignition and potion GameTest tick for tick."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/fluids/open_pipes.nbt")
EFFECTS_LEVER = "/setblock 5 99 -10 minecraft:lever[face=floor,facing=east,powered={}]"
REMOVERS_LEVER = "/setblock 6 100 -10 minecraft:lever[face=wall,facing=west,powered=false]"
LAVA_TARGET = "@e[type=minecraft:zombie,tag=OpenPipeLava,limit=1]"
POTION_TARGET = "@e[type=minecraft:zombie,tag=OpenPipePotion,limit=1]"
TANKS = ("5 98 -11", "5 98 -9", "7 100 -11", "7 100 -9")


def effects(reply):
    if "no elements matching" in reply.lower():
        return ""
    _, separator, data = reply.partition("has the following entity data: ")
    if not separator:
        raise RuntimeError(f"Unable to read the potion target: {reply}")
    readings = []
    for entry in re.findall(r"\{[^{}]*\}", data):
        name = re.search(r'\bid: "([a-z_:/]+)"', entry)
        duration = re.search(r"\bduration: (\d+)", entry)
        if name and duration:
            readings.append(f"{name[1]}={duration[1]}")
    return "|".join(sorted(readings))


def sample(control, tick, clock, applying):
    fire, active, *tanks = control.commands((
        f"/data get entity {LAVA_TARGET} Fire",
        f"/data get entity {POTION_TARGET} active_effects",
        *(f"/data get block {tank} TankContent" for tank in TANKS),
    ))
    fire_ticks = re.search(r"has the following entity data: (-?\d+)", fire)
    amounts = []
    for tank in tanks:
        _, separator, data = tank.partition("has the following block data: ")
        amount = re.search(r"\bamount: (\d+)", data)
        if not separator or (not amount and data != "{}"):
            raise RuntimeError(f"Missing or invalid tank data at tick {tick}: {tank}")
        amounts.append(amount[1] if amount else "0")
    if not fire_ticks:
        raise RuntimeError(f"Missing fire data at tick {tick}: {fire}")
    return [str(tick), str(clock % 5), str(applying).lower(),
            str(int(fire_ticks[1]) > 0).lower(), effects(active), *amounts]


def run(args):
    with (ROOT / "fixtures/open_pipes-java.csv").open() as source:
        reader = csv.reader(source)
        header, expected = next(reader), list(reader)
    actual = []
    with fixture_world(args, "Open-pipes", STRUCTURE) as control:
        start = control.clock()
        for target in range(start + 1, start + (int(expected[0][1]) - start) % 5 + 1):
            control.step_to(target)
        control.command("/place template create:gametest/fluids/open_pipes 3 96 -12")
        for z in (-11, -9):
            seat = control.command(f"/execute if block 7 97 {z} create:white_seat")
            if seat != "Test passed":
                raise RuntimeError(f"The original white seat at 7 97 {z} did not load: {seat}")
        control.commands((
            '/summon minecraft:zombie 7.5 97 -10.5 {Tags:["OpenPipeLava"]}',
            '/summon minecraft:zombie 7.5 97 -8.5 {Tags:["OpenPipePotion"]}',
            EFFECTS_LEVER.format("false"),
        ))
        start = control.clock()
        applying = True
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            row = sample(control, tick, start + tick, applying)
            actual.append(row)
            if applying and row[3] == "true" and row[4]:
                control.commands((EFFECTS_LEVER.format("true"), REMOVERS_LEVER))
                applying = False

    path = ROOT / ".local/open_pipes-horizon.csv"
    with path.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(a[0], {key: (left, right) for key, left, right in zip(header, a, b, strict=True)
                            if left != right}) for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"Open pipes differed at {len(differences)} ticks. "
                         f"First differences (Java, Horizon): {differences[:2]}. See {path}")
    print(f"Open pipe ignition, effects, and tank contents matched all {len(actual)} Java ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
