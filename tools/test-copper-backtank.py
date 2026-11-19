#!/usr/bin/env python3
"""Compare original Copper Backtank charging at low and high speed, dry and wet."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

POSITIONS = ((6, 176, 24), (9, 176, 24), (12, 176, 24))


def coords(values):
    return " ".join(map(str, values))


def setup(host):
    host.commands((
        "/fill 4 174 18 15 174 27 minecraft:stone",
        "/tp @s 8.5 175 21.5",
    ))
    for (x, y, z), wet, air, rpm in zip(
        POSITIONS, ("false", "false", "true"), (0, 883, 31), (16, 256, 256), strict=True
    ):
        host.commands((
            f"/setblock {x} {y} {z} create:copper_backtank[facing=north,waterlogged={wet}]",
            f"/data merge block {x} {y} {z} {{Air:{air},Timer:0}}",
            f"/setblock {x} {y + 1} {z} create:creative_motor[facing=down]",
        ))
        if rpm != 16:
            host.command(f"/data merge block {x} {y + 1} {z} {{ScrollValue:{rpm}}}")


def number(data, field, default=0):
    tag = re.search(rf"\b{field}: (-?\d+(?:\.\d+)?)[a-z]?", data)
    return float(tag[1]) if tag else default


def sample(host, tick):
    reads = host.commands(f"/data get block {coords(pos)}" for pos in POSITIONS)
    for lane, data in enumerate(reads):
        assert '"create:backtank"' in data, data
        rpm, air, timer = (number(data, field) for field in ("Speed", "Air", "Timer"))
        yield tick, lane, rpm, int(air), int(timer)


def verify(args):
    with (ROOT / "fixtures/copper-backtank-charging-java.csv").open(newline="") as file:
        rows = list(csv.DictReader(file))
    expected = [tuple(float(row[key]) for key in ("tick", "lane", "rpm", "air", "timer"))
                for row in rows]
    settled_signals = [int(row["comparator"]) for row in rows if row["tick"] == "35"]
    actual = []
    with fixture_world(args, "CopperBacktankCharging", pack=args.pack) as host:
        setup(host)
        start = host.clock()
        for tick in range(36):
            if tick:
                host.step_to(start + tick)
            actual.extend(sample(host, tick))
            x, y, z = POSITIONS[0]
            if tick == 9:
                host.command(f"/setblock {x} {y + 1} {z} minecraft:air")
            if tick == 14:
                host.commands((
                    f"/setblock {x} {y + 1} {z} create:creative_motor[facing=down]",
                    f"/data merge block {x} {y + 1} {z} {{ScrollValue:64}}",
                ))
        comparators = [(x + 1, y, z) for x, y, z in POSITIONS]
        host.commands(command for x, y, z in comparators for command in (
            f"/setblock {x} {y - 1} {z} minecraft:stone",
            f"/setblock {x} {y} {z} minecraft:comparator[facing=west]",
            f"/setblock {x} {y} {z + 1} minecraft:stone",
        ))
        for tick in (36, 37, 38):
            host.step_to(start + tick)
        outputs = host.commands(f"/data get block {coords(pos)} OutputSignal" for pos in comparators)
        signals = [int(re.search(r"(-?\d+)$", output)[1]) for output in outputs]

    with (ROOT / ".local/copper-backtank-horizon.csv").open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("tick", "lane", "rpm", "air", "timer"))
        writer.writerows(actual)
    differences = [(java, horizon) for java, horizon in zip(expected, actual, strict=True) if java != horizon]
    if differences:
        raise RuntimeError(f"{len(differences)} Backtank states differed. First (Java, Horizon) {differences[:10]}")
    assert signals == settled_signals, (signals, settled_signals)
    print(f"All {len(actual)} Java Backtank speed, air and timer samples matched.")
    print(f"Three settled comparator outputs matched Java: {signals}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
