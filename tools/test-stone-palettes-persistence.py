#!/usr/bin/env python3
"""Check representative decorative palette block states across save/reopen."""

import argparse
from pathlib import Path

from fixture_world import ROOT, fixture_world

CASES = (
    ((3, 97, 0), "create:cut_asurine_bricks"),
    ((4, 97, 0), "create:cut_asurine_slab[type=top]"),
    ((5, 97, 0), "create:cut_asurine_stairs[facing=east,half=top,shape=straight]"),
    ((6, 97, 0), "create:ochrum_pillar[axis=x]"),
    ((8, 97, 0), "create:cut_scoria_wall"),
    ((9, 97, 0), "create:cut_scoria_wall"),
)


def read_states(control):
    states = {}
    for pos, expected_block in CASES:
        observed = control.call("block", *pos)
        if observed["block"] != expected_block.split("[", 1)[0]:
            raise RuntimeError(f"Expected {expected_block} at {pos}, got {observed}")
        if "[" in expected_block:
            for prop in expected_block.split("[", 1)[1][:-1].split(","):
                key, value = prop.split("=", 1)
                if f"{key}={value}" not in observed["state"]:
                    raise RuntimeError(f"Expected {expected_block} at {pos}, got {observed}")
        states[pos] = observed["state"]
    if "east=low" not in states[(8, 97, 0)] or "west=low" not in states[(9, 97, 0)]:
        raise RuntimeError(f"Adjacent palette walls did not connect before save: {states}")
    return states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()

    with fixture_world(args, "StonePaletteReopen", pack=args.pack) as control:
        control.commands((
            "/fill 2 96 0 10 96 0 minecraft:stone",
            "/setblock 3 97 0 create:cut_asurine_bricks",
            "/setblock 4 97 0 create:cut_asurine_slab[type=top]",
            "/setblock 5 97 0 create:cut_asurine_stairs[facing=east,half=top,shape=inner_left]",
            "/setblock 6 97 0 create:ochrum_pillar[axis=x]",
            "/setblock 8 97 0 create:cut_scoria_wall",
            "/setblock 9 97 0 create:cut_scoria_wall",
        ))
        before = read_states(control)
        control.command("/save-all")
        control.restart()
        after = read_states(control)
        if after != before:
            raise RuntimeError(f"Palette block states changed across save/reopen: {before} -> {after}")

    print("Full block, top slab, oriented stair, horizontal pillar, and connected walls retained their states across save/reopen.")


if __name__ == "__main__":
    main()
