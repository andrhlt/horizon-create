#!/usr/bin/env python3
"""Replay the original stone_cobble_sand_crushing factory in Horizon."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/stone_cobble_sand_crushing.nbt")
COUNT = re.compile(r'\b(?:Count|count): (\d+)')
ID = re.compile(r'\bid: "([\w:]+)"')


def field(text, name, default=None):
    value = re.search(rf"\b{name}: (-?\d+(?:\.\d+)?)", text)
    if value:
        return value[1]
    if default is not None:
        return default
    raise RuntimeError(f"Missing {name} in {text}")


def stack_fragments(text):
    return re.findall(r'\{(?:[^{}]|\{[^{}]*\})*\}', text)


def sample(control, tick):
    responses = iter(control.commands([
        command
        for y in (0, 3)
        for command in (
            f"/data get block 4 {98+y} -10 Items",
            f"/data get block 5 {97+y} -10 Inventory",
            f"/data get block 7 {98+y} -10",
            f"/data get block 7 {98+y} -10 Items",
        )
    ] + [f"/data get block 10 {y} -10 ItemPosition" for y in range(98, 102)]
      + [f"/data get block 10 {y} -10 Items" for y in range(98, 102)]))
    result = []
    for lane in range(2):
        chest, belt, crusher, inventory = (next(responses) for _ in range(4))
        belt_stacks = []
        for piece in stack_fragments(belt):
            if "Item:" not in piece:
                continue
            label, count = ID.search(piece), COUNT.search(piece)
            if label and count and int(count[1]):
                belt_stacks.append(f"{label[1]}:{count[1]}:{float(field(piece,'Pos')):.7f}")
        crusher_stacks = []
        for piece in stack_fragments(inventory):
            label, count = ID.search(piece), COUNT.search(piece)
            if label and count:
                crusher_stacks.append(f"{field(piece,'Slot','0')}:{label[1]}:{count[1]}")
        result.append([str(tick), f"crusher{lane}", field(crusher, "Speed", "0"),
                       field(crusher, "ProcessingTime", "0"), field(crusher, "AppliedRecipe", "0"),
                       str(sum(map(int, COUNT.findall(chest)))),
                       ";".join(belt_stacks), ";".join(sorted(crusher_stacks))])
    positions = [next(responses) for _ in range(4)]
    for lane, position in enumerate(positions):
        items = next(responses)
        label, count = ID.search(items), COUNT.search(items)
        motion = re.search(r'has the following block data: (-?\d+(?:\.\d+)?)', position)
        result.append([str(tick), f"chute{lane}", motion[1] if motion else "0", "", "", "",
                       f"{label[1]}:{count[1]}" if label and count else "", ""])
    return result


def equal(a, b):
    if a[:2] != b[:2] or a[4:6] != b[4:6] or a[7] != b[7]:
        return False
    for old, new in zip(a[2:4], b[2:4], strict=True):
        if old and abs(float(old) - float(new)) > 0.000001:
            return False
    if a[1].startswith("chute"):
        return a[6] == b[6]
    old = [stack.rsplit(":",1) for stack in a[6].split(";") if stack]
    new = [stack.rsplit(":",1) for stack in b[6].split(";") if stack]
    return len(old) == len(new) and all(
        left[0] == right[0] and abs(float(left[1])-float(right[1])) <= 0.000001
        for left, right in zip(old, new, strict=True)
    )


def run(args):
    with (ROOT / "fixtures/stone_cobble_sand_crushing-java.csv").open() as file:
        reader = csv.reader(file)
        header, expected = next(reader), list(reader)
    last = int(expected[-1][0])
    actual = []
    with fixture_world(args, "Stone-crushing", STRUCTURE, env={"CREATE_FAN_TRACE_SEED": "4096"}) as control:
        control.command("/place template create:gametest/processing/stone_cobble_sand_crushing 3 96 -12")
        control.command("/setblock 5 98 -11 minecraft:lever[face=floor,facing=south,powered=false]")
        start = control.clock()
        for tick in range(last + 1):
            if tick:
                control.step_to(start + tick)
            actual.extend(sample(control, tick))
        receiver = control.command("/data get block 4 101 -10 Items")
        finished = {}
        for stack in stack_fragments(receiver):
            label, count = ID.search(stack), COUNT.search(stack)
            if label and count:
                finished[label[1]] = finished.get(label[1], 0) + int(count[1])
        if finished != {"minecraft:sand": 5, "minecraft:flint": 1}:
            raise RuntimeError(f"Expected five sand and one flint, got {receiver}")

    path = ROOT / ".local/stone_cobble_sand_crushing-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    different = [(a,b) for a,b in zip(expected, actual, strict=True) if not equal(a,b)]
    if different:
        raise SystemExit(f"Crushing differs on {len(different)} rows. First rows (Java, Horizon): "
                         f"{different[:12]}. See {path}")
    print(f"Original two-stage crushing fixture matched Java across {last+1} ticks. See {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl","client","resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())


if __name__ == "__main__":
    main()
