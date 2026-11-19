#!/usr/bin/env python3
"""Replay the original Java Schematicannon GameTest."""
import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/misc/schematicannon.nbt")
CANNON = (6, 97, -6)
ANCHOR = (4, 97, -11)
SIZE = (1, 3, 7)
TEMPLATE = "create:schematicannon_replay"
TARGET = re.compile(r"\bTarget: \[I; (-?\d+), (-?\d+), (-?\d+)\]")
TICKS = re.compile(r"\bTicksLeft: (-?\d+)")


def location(pos):
    return " ".join(map(str, pos))


def load_print(control):
    replies = control.commands((
        "/place template create:gametest/misc/schematicannon 3 96 -12",
        "/setblock 8 105 -11 minecraft:structure_block[mode=save]",
        f'/data merge block 8 105 -11 {{name:"{TEMPLATE}",mode:"SAVE",posX:0,posY:-8,'
        'posZ:0,sizeX:1,sizeY:3,sizeZ:7,ignoreEntities:0b,powered:0b}',
        "/setblock 8 105 -10 minecraft:redstone_block",
        f'/data merge block {location(CANNON)} {{State:"RUNNING",Status:"running",'
        'Items:[{Slot:0b,id:"create:schematic",count:1,components:'
        f'{{"minecraft:custom_data":{{Template:"{TEMPLATE}",Anchor:[I;4,97,-11]}}}}}}]}}',
    ))
    if control.call("block", *CANNON)["state"] != "create:schematicannon":
        raise RuntimeError(f"Missing cannon in original structure. {replies}")


def read_cannon(control):
    reply, flying = control.commands((f"/data get block {location(CANNON)}",
                                     f"/data get block {location(CANNON)} FlyingBlocks"))
    if " has the following block data: " not in reply:
        raise RuntimeError(f"Could not read cannon state. {reply}")
    def field(name, pattern, default=None):
        if match := re.search(rf"\b{name}: ({pattern})", reply):
            return match[1]
        if default is not None:
            return default
        raise RuntimeError(f"Missing {name}. {reply}")
    state = field("State", r'"[A-Z]+"').strip('"')
    status = field("Status", r'"[\w]+"').strip('"')
    fuel = field("RemainingFuel", r"-?\d+", "0")
    placed = field("AmountPlaced", r"\d+")
    total = field("AmountToPlace", r"\d+")
    progress = f'{float(field("Progress", r"[\d.E-]+")):.6f}'
    flights = []
    for target, remaining in zip(TARGET.finditer(flying), TICKS.findall(flying), strict=True):
        relative = [int(a) - b for a, b in zip(target.groups(), ANCHOR, strict=True)]
        flights.append(":".join(map(str, (*relative, remaining))))
    far = tuple(a + size - 1 for a, size in zip(ANCHOR, SIZE, strict=True))
    report = control.call("blocks", *ANCHOR, *far)
    blocks = {(x, y, z): state.split("[", 1)[0] for x, y, z, state in report["blocks"]}
    targets = ((ANCHOR[0], y, z) for y in range(ANCHOR[1], far[1] + 1)
               for z in range(ANCHOR[2], far[2] + 1))
    output = "|".join(blocks.get(at, "minecraft:air") for at in targets)
    return [state, status, fuel, placed, total, progress, "|".join(flights), output]


def run(args):
    with (ROOT / "fixtures/schematicannon-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)[:args.ticks]
    with fixture_world(args, "Schematicannon", STRUCTURE) as control:
        time = control.clock()
        for target in range(time + 1, time + (int(expected[0][1]) - time) % 20 + 1):
            control.step_to(target)
        load_print(control)
        start = control.clock()
        actual = []
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append([str(tick), str((start + tick) % 20), *read_cannon(control)])
        if expected[-1][2:4] == ["STOPPED", "finished"]:
            output = control.command(f"/data get block {location(CANNON)} Items")
            if "create:empty_schematic" not in output:
                raise RuntimeError(f"The completed schematic was not returned. {output}")
    path = ROOT / ".local/schematicannon-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want[0], {name: (a, b) for name, a, b in zip(header, want, got, strict=True) if a != b})
                   for want, got in zip(expected, actual, strict=True) if want != got]
    if differences:
        raise SystemExit(f"Schematicannon differed at {len(differences)} ticks. "
                         f"First differences (Java, Horizon) {differences[:2]}. See {path}")
    print(f"Schematicannon matched all {len(actual)} Java ticks. See {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("ctl", "client", "resources"):
        parser.add_argument(argument, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()
    if args.ticks is not None and args.ticks < 1:
        parser.error("--ticks must be positive")
    run(args)
