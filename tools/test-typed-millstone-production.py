#!/usr/bin/env python3
"""Exercise the real Create wheat milling recipe and output backpressure."""

import argparse
from pathlib import Path

from fixture_world import fixture_world


MILL = (0, 100, 0)
PROCESSING_TICKS = 155


def xyz(pos):
    return " ".join(map(str, pos))


def block_data(control):
    return control.command(f"/data get block {xyz(MILL)}")


def advance(control, ticks):
    for _ in range(ticks):
        control.step_to(control.clock() + 1)


def require_flour(data):
    if "create:wheat_flour" not in data or "count: 1" not in data:
        raise RuntimeError(f"Real wheat milling did not produce one flour: {data}")


def verify(args):
    with fixture_world(args, "TypedMillstoneProduction", pack=args.pack) as control:
        control.commands((
            f"/setblock {xyz(MILL)} create:millstone",
            f"/data merge block {xyz(MILL)} {{Speed:16.0f}}",
            f"/item replace block {xyz(MILL)} container.0 with minecraft:wheat 1",
        ))
        advance(control, PROCESSING_TICKS)
        completed = block_data(control)
        if "minecraft:wheat" in completed:
            raise RuntimeError(f"Real wheat input was not consumed: {completed}")
        require_flour(completed)

        control.call("save")
        control.restart()
        reopened = block_data(control)
        require_flour(reopened)

        control.commands((
            f"/item replace block {xyz(MILL)} container.1 with create:wheat_flour 64",
            f"/item replace block {xyz(MILL)} container.0 with minecraft:wheat 1",
        ))
        advance(control, PROCESSING_TICKS)
        blocked = block_data(control)
        if "minecraft:wheat" not in blocked:
            raise RuntimeError(f"Full output slot caused input loss: {blocked}")
        if "create:wheat_flour" not in blocked or "count: 64" not in blocked:
            raise RuntimeError(f"Full output slot changed unexpectedly: {blocked}")

    print("Typed Millstone matched real wheat milling, retained output across reopen, and conserved input under full output.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
