#!/usr/bin/env python3
"""Compare natural Copper Roof weathering state order with Java Create."""
import argparse
from pathlib import Path

from fixture_world import ROOT, fixture_world
POSITIONS = ((5, 100, 8), (11, 100, 8), (17, 100, 8),
             (5, 100, 14), (11, 100, 14), (17, 100, 14))
STONE = (23, 100, 14)


def observe(world, positions):
    return [reply["state"] for reply in world.call(
        "script", script="".join(f"block {x} {y} {z}\n" for x, y, z in positions)
    )]


def main():
    parser = argparse.ArgumentParser()
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    expected = [row.split(";") for row in (ROOT / "fixtures/copper-roof-oxidation-java.txt").read_text().splitlines()]
    positions = (*POSITIONS, STONE)
    results = [[] for _ in positions]
    with fixture_world(args, "CopperRoofOxidation", pack=args.pack) as world:
        world.commands((
            "/fill 2 99 4 24 99 18 minecraft:smooth_stone",
            "/tp @s 10.5 100 18.5",
            "/gamerule random_tick_speed 8192",
            *(f"/setblock {x} {y} {z} {row[0]}"
              for (x, y, z), row in zip(POSITIONS, expected, strict=True)),
            "/setblock 23 100 14 minecraft:copper_block",
        ))
        start = world.clock()
        for tick in range(230):
            if tick:
                world.step_to(start + tick)
            for history, state in zip(results, observe(world, positions), strict=True):
                if not history or history[-1] != state:
                    history.append(state)
            if tick >= 25 and all(len(h) >= end for h, end in
                                  zip(results, [*(len(h) for h in expected), 4], strict=True)):
                break
    for phase in results:
        print(";".join(phase), flush=True)
    print(f"Observed {tick + 1} world ticks.", flush=True)
    if len(results[-1]) < 4:
        raise AssertionError(f"Vanilla fresh copper did not age through its four states: {results[-1]}")
    if results[:-1] != expected:
        raise AssertionError(f"Expected original stages {expected}, got {results[:-1]}")


if __name__ == "__main__":
    main()
