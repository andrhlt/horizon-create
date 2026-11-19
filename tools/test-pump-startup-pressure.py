#!/usr/bin/env python3
"""Check the legacy pump's own and surrounding pressure on its facing flip."""

import argparse
import csv
from pathlib import Path

from importlib import import_module
from fixture_world import ROOT, fixture_world

pipes = import_module("test-encased-fluid-pipe")
branched = import_module("test-branched-pipes")
entity_data = import_module("test-depot-ejector-obstacle")


def port(data, side):
    pressure = entity_data.vector(pipes.compound(data, side), "Pressure") or (0.0, 0.0)
    return f"{pressure[0]:.4f}:{pressure[1]:.4f}"


def sample(host, mode, tick):
    pump_pos = branched.PUMP
    pump, junction, west, east = host.commands((
        f"/data get block {pump_pos}",
        f"/data get block {pipes.coords(pipes.TRANSFER_PIPE)}",
        f"/execute if block {pump_pos} create:mechanical_pump[facing=west]",
        f"/execute if block {pump_pos} create:mechanical_pump[facing=east]",
    ))
    directions = [side for side, result in (("west", west), ("east", east)) if result.startswith("Test passed")]
    if len(directions) != 1:
        raise RuntimeError(f"Wrong pump orientation sample at {mode} tick {tick}: {west}, {east}")
    return [mode, str(tick), directions[0], f'{branched.reading(pump, "Speed"):.4f}',
            *(port(pump, side) for side in ("west", "east")),
            *(port(junction, side) for side in ("west", "east", "north", "south"))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/pump-startup-pressure-horizon.csv")
    args = parser.parse_args()
    with (ROOT / "fixtures/pump-startup-pressure-java.csv").open(newline="") as source:
        reader = csv.reader(source)
        header, expected = next(reader), list(reader)

    actual = []
    for mode, facing in (("combine", "east"), ("split", "west")):
        template = f"gametest/fluids/3_pipe_{mode}"
        with fixture_world(args, f"PumpStartupPressure-{mode}", Path(template + ".nbt"), pack=args.pack,
                           env={"HORIZON_NO_AUDIO": "1"}) as host:
            host.commands((
                f"/place template create:{template} 3 96 -12",
                f"/setblock {branched.PUMP} create:mechanical_pump[facing={facing},waterlogged=false]",
            ))
            clock = host.clock()
            for tick in range(4):
                if tick:
                    host.step_to(clock + tick)
                actual.append(sample(host, mode, tick))

    with args.output.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    misses = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    if misses:
        raise RuntimeError(f"{len(misses)} pressure samples differed. Java and Horizon: {misses}")
    print("Both legacy pump facing flips matched all eight Java pressure samples.")


if __name__ == "__main__":
    main()
