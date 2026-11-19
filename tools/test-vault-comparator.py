#!/usr/bin/env python3
"""Compare the original vault fixture's inventories and redstone on every Java tick."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/items/vault_comparator_output.nbt")
LANES = (
    ((4, 97, -11), 1, (5, 97, -11), (6, 97, -11), (4, 99, -11), 9),
    ((4, 97, -9), 2, (6, 97, -8), (7, 97, -8), (4, 100, -8), 77),
    ((4, 97, -6), 3, (7, 97, -5), (8, 97, -5), (4, 101, -4), 240),
)
COUNT = re.compile(r'\b(?:Count|count): (\d+)')
VALUE = re.compile(r'has the following block data: (-?\d+)')


def spawn(control, lane):
    _, _, _, _, target, stacks = LANES[lane]
    x, y, z = (value + 0.5 for value in target)
    for batch in range(0, stacks, 40):
        suffix = '{Item:{id:"minecraft:bread",count:64},Motion:[0.0d,0.0d,0.0d]}'
        command = f"/summon minecraft:item {x} {y} {z} {suffix}"
        replies = control.commands([command] * min(40, stacks - batch))
        if any("Summoned new" not in reply for reply in replies):
            raise RuntimeError(f"Could not add the fixture's bread to lane {lane}: {replies[0]}")


def position(coords):
    return " ".join(map(str, coords))


def sample(control, tick):
    commands = []
    for (x, y, z), size, comp, nixie, _, _ in LANES:
        commands.extend((f"/data get block {position(comp)} OutputSignal",
                         f"/data get block {position(nixie)} RedstoneStrength"))
        commands.extend(
            f"/data get block {x + a} {y + b} {z + c} Items"
            for a in range(size) for b in range(size) for c in range(size)
        )
    replies = iter(control.commands(commands))
    rows = []
    for lane, (_, size, _, _, _, _) in enumerate(LANES):
        comp, nixie = [VALUE.search(next(replies)) for _ in range(2)]
        if not comp or not nixie:
            raise RuntimeError(f"Could not read the comparator and Nixie in lane {lane}")
        total = sum(sum(map(int, COUNT.findall(next(replies)))) for _ in range(size ** 3))
        rows.append([str(tick), str(lane), str(total), comp[1], nixie[1]])
    return rows


def run(args):
    reference = ROOT / "fixtures/vault_comparator_output-java.csv"
    with reference.open() as file:
        expected = [
            [row[key] for key in ("tick", "lane", "items", "comparator", "nixie")]
            for row in csv.DictReader(file)
        ]
    active_rows = {(int(row[0]), int(row[1])) for row in expected}
    actual = []
    with fixture_world(args, "Vault-comparator", STRUCTURE) as control:
        control.command("/place template create:gametest/items/vault_comparator_output 3 96 -12")
        start = control.clock()
        for tick in range(int(expected[-1][0]) + 1):
            if tick:
                control.step_to(start + tick)
            # Java's GameTest callback spawns the bread after the world tick.
            if tick in (20, 40, 60):
                spawn(control, tick // 20 - 1)
            actual.extend(row for lane, row in enumerate(sample(control, tick))
                          if (tick, lane) in active_rows)

    path = ROOT / ".local/vault_comparator_output-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("tick", "lane", "items", "comparator", "nixie"))
        writer.writerows(actual)
    differences = [(a, b) for a, b in zip(expected, actual, strict=True) if a != b]
    if differences:
        raise SystemExit(f"Vaults differ on {len(differences)} rows. "
                         f"First rows (Java, Horizon): {differences[:8]}. See {path}")
    print(f"Original vault comparator fixture matched {int(expected[-1][0]) + 1} Java ticks. See {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())


if __name__ == "__main__":
    main()
