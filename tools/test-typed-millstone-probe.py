#!/usr/bin/env python3
"""Run a synthetic milling recipe through the typed Millstone adapter."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world

MILL = (0, 100, 0)


def xyz(pos):
    return " ".join(map(str, pos))


def block_data(control):
    return control.command(f"/data get block {xyz(MILL)}")


def advance(control, ticks):
    for _ in range(ticks):
        control.step_to(control.clock() + 1)


def verify(args):
    with fixture_world(args, "TypedMillstoneProbe", pack=args.pack) as control:
        control.commands((
            f"/setblock {xyz(MILL)} create:millstone",
            f"/data merge block {xyz(MILL)} {{Speed:16.0f}}",
            f"/item replace block {xyz(MILL)} container.0 with minecraft:wheat 1",
        ))
        advance(control, 4)
        completed = block_data(control)
        if re.search(r"Slot: 0b", completed) is not None:
            raise RuntimeError(f"Millstone did not consume the recipe input: {completed}")
        if "minecraft:bread" not in completed or "count: 1" not in completed:
            raise RuntimeError(f"Millstone did not insert the declared recipe output: {completed}")

        control.command(f"/data merge block {xyz(MILL)} {{Speed:0.0f}}")
        control.command(f"/item replace block {xyz(MILL)} container.0 with minecraft:wheat 1")
        control.call("save")
        control.restart()
        advance(control, 4)
        idle = block_data(control)
        if "minecraft:wheat" not in idle:
            raise RuntimeError(f"Zero-speed Millstone lost its unprocessed input: {idle}")
        if "minecraft:bread" not in idle:
            raise RuntimeError(f"Millstone output did not survive save/reopen: {idle}")
    print("Typed Millstone completed the synthetic wheat recipe at 16 RPM and retained inventory while idle after reopen.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
