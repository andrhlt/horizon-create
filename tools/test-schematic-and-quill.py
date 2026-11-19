#!/usr/bin/env python3
"""Check the original Schematic and Quill survival crafting recipe."""

import argparse
from pathlib import Path
from runpy import run_path

from fixture_world import fixture_world

helpers = run_path(str(Path(__file__).with_name("test-survival-crafting.py")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with fixture_world(args, "Schematic-and-quill", render=True, pack=args.pack) as control:
        control.commands((
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:empty_schematic",
            "/item replace entity @s hotbar.1 with minecraft:feather",
        ))
        control.call("open-inventory")
        helpers["distribute"](control, 0, (100,))
        helpers["distribute"](control, 1, (101,))
        helpers["craft"](control, "create:schematic_and_quill", 1)
        counts = control.call("inventory")["counts"]
        if counts.get("create:empty_schematic", 0) or counts.get("minecraft:feather", 0):
            raise RuntimeError(f"Crafting did not consume both ingredients: {counts}")
    print("Schematic and Quill crafted from an empty schematic and a feather.")


if __name__ == "__main__":
    main()
