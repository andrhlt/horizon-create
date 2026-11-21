#!/usr/bin/env python3
"""Check connected and waterlogged window panes survive a cold world reopen."""

import argparse
from pathlib import Path

from fixture_world import fixture_world


FIRST = (8, 97, -9)
SECOND = (9, 97, -9)


def state(world, position):
    result = world.call("block", *position)
    properties = {}
    if "[" in result["state"]:
        properties = dict(
            entry.split("=", 1)
            for entry in result["state"].split("[", 1)[1][:-1].split(",")
        )
    return result["block"], properties


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()

    with fixture_world(args, "Window-reopen", render=False, pack=args.pack) as world:
        world.commands((
            "/fill 7 96 -10 10 96 -8 minecraft:smooth_stone",
            "/fill 7 97 -10 10 100 -8 minecraft:air",
            f"/setblock {FIRST[0]} {FIRST[1]} {FIRST[2]} create:oak_window_pane[east=true]",
            f"/setblock {SECOND[0]} {SECOND[1]} {SECOND[2]} create:oak_window_pane[west=true,waterlogged=true]",
        ))
        before = tuple(state(world, position) for position in (FIRST, SECOND))
        expected = (
            ("create:oak_window_pane", {"east": "true", "north": "false", "south": "false", "waterlogged": "false", "west": "false"}),
            ("create:oak_window_pane", {"east": "false", "north": "false", "south": "false", "waterlogged": "true", "west": "true"}),
        )
        if before != expected:
            raise RuntimeError(f"Unexpected pane states before save: {before}")
        world.call("save")
        world.restart()
        after = tuple(state(world, position) for position in (FIRST, SECOND))
        if after != before:
            raise RuntimeError(f"Connected/waterlogged panes changed across reopen: {before} -> {after}")

    print("Connected and waterlogged panes retained their block states across cold save/reopen; active state is not applicable to static blocks.")


if __name__ == "__main__":
    main()
