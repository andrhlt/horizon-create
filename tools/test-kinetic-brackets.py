#!/usr/bin/env python3
"""Compare shaft and cog bracket attachment, replacement, wrench return, and drops."""

import argparse
import csv
import importlib.util
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

SHAFT = (8, 101, -10)
COG = (14, 101, -10)
INVALID = (18, 101, -10)
WOOD, METAL, WRENCH = "create:wooden_bracket", "create:metal_bracket", "create:wrench"


def coords(pos):
    return " ".join(map(str, pos))


def setup(control):
    control.commands((
        "/fill 4 100 -15 20 100 -5 minecraft:smooth_stone",
        "/fill 4 101 -15 20 103 -5 minecraft:air",
        f"/setblock {coords(SHAFT)} create:shaft[axis=x]",
        f"/setblock {coords(COG)} create:cogwheel[axis=y]",
        f"/setblock {coords(INVALID)} minecraft:stone",
        "/gamemode survival",
        f"/item replace entity @s hotbar.0 with {WOOD} 2",
        f"/item replace entity @s hotbar.1 with {METAL} 2",
        f"/item replace entity @s hotbar.2 with {WRENCH} 1",
    ))


def press(control, item, pos, face, *, teleport=True):
    x, y, z = pos
    camera_z = z + 2.55 if face == "south" else z - 2.0
    if teleport:
        control.command(f"/tp @s {x + 0.5} {y} {camera_z:.2f}")
        control.call("wait", 3)
    control.call("select", item)
    if face == "south":
        control.call("look-at", x + 0.5, y + 0.5, z + 0.998)
    else:
        control.call("look-at", x + 0.5, y + (0.998 if pos == INVALID else 0.685), z + 0.5)
    control.call("wait", 2)
    control.call("mouse", "right", "down")
    control.call("wait", 1)
    control.call("mouse", "right", "up")
    control.call("wait", 3)


def attached(nbt):
    material = re.search(r'\bName: "create:(wooden|metal)_bracket"', nbt)
    if material is None:
        return ("none", "none", "none", "false")
    prop = lambda key: re.search(rf'\b{key}: "([a-z]+)"', nbt)[1]
    return ("wood" if material[1] == "wooden" else "metal", prop("type"), prop("facing"), prop("axis_along_first"))


def sample(control, tick):
    shaft, cog = control.commands((
        f"/data get block {coords(SHAFT)} Bracket",
        f"/data get block {coords(COG)} Bracket",
    ))
    counts = control.call("inventory")["counts"]
    dropped = sum(entity["item"]["count"] for entity in control.call("entities", 24, "minecraft:item")["entities"]
                  if entity["item"]["item"] == WOOD)
    return (str(tick), *attached(shaft), *attached(cog), str(counts.get(WOOD, 0)), str(counts.get(METAL, 0)), str(dropped))


def verify(args):
    with (ROOT / "fixtures/kinetic-brackets-java.csv").open() as stream:
        _, _, *expected = list(csv.reader(stream))
    actions = {2: (WOOD, INVALID, "up"), 3: (WOOD, SHAFT, "up"), 4: (WOOD, SHAFT, "up"),
               5: (METAL, SHAFT, "up"), 7: (WRENCH, SHAFT, "up"), 8: (WOOD, COG, "south")}
    actual = []
    with fixture_world(args, "KineticBrackets", render=True, pack=args.pack) as control:
        setup(control)
        start = control.clock()
        for row in expected:
            tick = int(row[0])
            control.step_to(start + tick)
            actual.append(sample(control, tick))
            if args.frames and tick in (3, 4, 6, 8, 9):
                control.call("screenshot", args.frames / f"bracket-{tick}.png")
            if tick in actions:
                press(control, *actions[tick])
            if tick == 10:
                control.command(f"/setblock {coords(COG)} minecraft:air destroy")
                control.call("wait", 2)
    wanted = list(map(tuple, expected))
    if actual != wanted:
        diffs = [(want, got) for want, got in zip(wanted, actual, strict=True) if want != got]
        raise RuntimeError(f"{len(diffs)} bracket differences. First six: {diffs[:6]}")
    print(f"Bracket attachment, replacement, wrench return, and cog drops matched Java across {len(actual)} simulated ticks.")


def craft(args):
    path = ROOT / "tools/test-electronics-crafting.py"
    spec = importlib.util.spec_from_file_location("crafting", path)
    crafting = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(crafting)
    crafting.RECIPES = (
        ("wooden_bracket", 4, (("minecraft:stick", (100, 101, 102)),
                               ("minecraft:oak_planks", (103, 105)), ("create:andesite_alloy", (104,)))),
        ("metal_bracket", 4, (("minecraft:iron_nugget", (100, 101, 102)),
                              ("minecraft:iron_ingot", (103, 105)), ("create:andesite_alloy", (104,)))),
    )
    def exact_world(*world_args, **kwargs):
        return fixture_world(*world_args, **kwargs, pack=args.pack)
    crafting.fixture_world = exact_world
    crafting.run(args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--frames", type=Path)
    parser.add_argument("--craft", action="store_true")
    args = parser.parse_args()
    if args.frames:
        args.frames.mkdir(parents=True, exist_ok=True)
    (craft if args.craft else verify)(args)


if __name__ == "__main__":
    main()
