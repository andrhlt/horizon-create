#!/usr/bin/env python3
"""Check representative copper roof age, wax, and shape across save/reopen."""

import argparse
from pathlib import Path

from fixture_world import fixture_world

POSITIONS = ((5, 100, 5), (8, 100, 5), (11, 100, 5),
             (14, 100, 5), (17, 100, 5), (20, 100, 5))
STATES = (
    "create:copper_shingles",
    "create:waxed_exposed_copper_tiles",
    "create:weathered_copper_shingle_slab[type=top,waterlogged=true]",
    "create:waxed_oxidized_copper_tile_slab[type=double,waterlogged=false]",
    "create:exposed_copper_shingle_stairs[facing=east,half=top,shape=straight,waterlogged=true]",
    "create:waxed_weathered_copper_tile_stairs[facing=west,half=bottom,shape=outer_right,waterlogged=false]",
)


def read_states(control):
    return tuple(control.call("block", *pos)["state"] for pos in POSITIONS)


def verify(args):
    with fixture_world(args, "CopperRoofPersistence", pack=args.pack) as control:
        control.command("/gamerule random_tick_speed 0")
        control.commands(f"/setblock {' '.join(map(str, pos))} {state}"
                         for pos, state in zip(POSITIONS, STATES, strict=True))
        before = read_states(control)
        if before != STATES:
            raise RuntimeError(f"Copper roof fixture did not reach its requested states: {before}")
        control.call("save")
        control.restart()
        after = read_states(control)
        if after != before:
            raise RuntimeError(f"Copper roof age/wax/shape changed across save/reopen: {before} -> {after}")
    print(f"Copper roof age, wax, slab/stair shape, and waterlogging survived save/reopen ({len(STATES)} states).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
