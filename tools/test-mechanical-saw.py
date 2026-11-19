#!/usr/bin/env python3
"""Replay the filtered item cut and horizontal trunk cut measured in Java Create."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

ITEM_SAW = (8, 180, 8)
BLOCK_SAW = (8, 180, 22)
TRUNK = (9, 180, 22)
UPPER = (9, 181, 22)
FIELDS = (
    "item_rpm", "remaining", "duration", "applied", "input", "output", "mosaic",
    "diamond", "block_rpm", "progress", "next_tick", "target", "upper",
)
ACTION_TICKS = {
    3: ('/summon minecraft:item 8.5 180.79 8.5 {Item:{id:"minecraft:bamboo_planks",count:1},'
        'Motion:[0.0d,0.0d,0.0d]}',),
    8: ("/setblock 9 180 22 minecraft:oak_log", "/setblock 9 181 22 minecraft:oak_log"),
    65: ('/summon minecraft:item 8.5 180.79 8.5 {Item:{id:"minecraft:diamond",count:1},'
         'Motion:[0.0d,0.0d,0.0d]}',),
}


def xyz(pos):
    return " ".join(map(str, pos))


def fields_at(pos, *keys):
    return (f"/data get block {xyz(pos)} {key}" for key in keys)


def number(reply, *, default=None):
    result = re.search(r"(-?\d+(?:\.\d+)?)[bfsdL]?$", reply)
    if result is None:
        if default is None:
            raise RuntimeError(f"Could not read saw field: {reply}")
        return default
    return float(result[1])


def drop(item):
    return (f'/execute if entity @e[type=minecraft:item,x=4,y=179,z=4,dx=12,dy=3,dz=10,'
            f'nbt={{Item:{{id:"{item}"}}}}]')


def count(reply):
    return 0 if "Test passed" not in reply else int(number(reply, default=1))


def setup(control, output="minecraft:bamboo_mosaic"):
    controls = (
        "/fill 5 179 3 14 179 26 minecraft:smooth_stone",
        "/setblock 8 180 8 create:mechanical_saw[facing=up,axis_along_first=false]",
        "/setblock 8 180 22 create:mechanical_saw[facing=east]",
        "/setblock 9 180 22 minecraft:stone",
        "/setblock 8 180 7 create:creative_motor[facing=south]{ScrollValue:96}",
        "/setblock 7 180 22 create:creative_motor[facing=east]{ScrollValue:96}",
        '/data merge block 8 180 8 {Filter:{id:"%s",count:1}}' % output,
        "/tp @s 8.5 182 12",
    )
    for command, reply in zip(controls, control.commands(controls), strict=True):
        marker = "Changed the block" if command.startswith("/setblock ") else None
        if marker is not None and marker not in reply:
            raise RuntimeError(f"Setup failed for {command}: {reply}")
    for _ in range(2):
        control.step_to(control.clock() + 1)


def sample(control, output):
    replies = control.commands((
        *fields_at(ITEM_SAW, "Speed", "ProcessingTime", "RecipeTime", "AppliedRecipe",
                   "Items[{Slot:0b}].count", "Items[{Slot:1b}].count"),
        drop(output), drop("minecraft:diamond"),
        *fields_at(BLOCK_SAW, "Speed", "Progress", "NextTick"),
    ))
    return (
        *(f"{number(reply):.2f}" for reply in replies[:3]),
        str(int(number(replies[3]))),
        *(str(int(number(reply, default=0))) for reply in replies[4:6]),
        *(str(count(reply)) for reply in replies[6:8]),
        f"{number(replies[8]):.2f}",
        *(str(int(number(reply))) for reply in replies[9:]),
        *(control.call("block", *target)["block"] for target in (TRUNK, UPPER)),
    )


def run(args):
    fixture = "runtime-saw" if args.runtime else "mechanical-saw"
    output = "minecraft:spruce_trapdoor" if args.runtime else "minecraft:bamboo_mosaic"
    fields = tuple("trapdoor" if args.runtime and field == "mosaic" else field for field in FIELDS)
    with (ROOT / f"fixtures/{fixture}-java.csv").open() as file:
        expected = tuple(csv.DictReader(file))
    with fixture_world(args, fixture, render=args.visual, pack=args.pack) as control:
        setup(control, output)
        if args.visual:
            control.call("look-at", 8.5, 180.6, 8.5)
            control.call("key", "f1", "tap")
        start = control.clock()
        differences = []
        with (ROOT / f".local/{fixture}-horizon.csv").open("w") as file:
            writer = csv.writer(file)
            writer.writerow(("tick", *fields))
            for row in expected:
                tick = int(row["tick"])
                if tick:
                    control.step_to(start + tick)
                actual = sample(control, output)
                writer.writerow((tick, *actual))
                for key, value in zip(fields, actual, strict=True):
                    if value != row[key]:
                        differences.append(f"Tick {tick}, {key}: Horizon {value}, Java {row[key]}")
                if differences and not args.diagnostics:
                    raise RuntimeError(differences[-1])
                if args.visual and tick == 9:
                    control.call("screenshot", ROOT / ".local/mechanical-saw.png")
                if actions := ACTION_TICKS.get(tick):
                    control.commands(
                        command.replace("minecraft:bamboo_planks", "minecraft:spruce_planks")
                        if args.runtime else command
                        for command in actions
                    )
        if differences:
            raise RuntimeError("\n".join(differences[:20]))
    print(f"Mechanical Saw item processing and horizontal cutting matched {len(expected)} Java ticks.")


def configure(args):
    with fixture_world(args, "Mechanical-saw-placement", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 6 179 6 14 179 14 minecraft:smooth_stone",
            "/setblock 9 180 8 create:shaft[axis=x]",
            "/setblock 9 180 12 minecraft:smooth_stone",
            "/item replace entity @s hotbar.0 with create:mechanical_saw 2",
            "/item replace entity @s hotbar.1 with minecraft:bamboo_mosaic 2",
            "/tp @s 8.5 182 8.5",
        ))
        control.call("select", "create:mechanical_saw")
        control.call("look-at", 8.5, 180.0, 8.5)
        control.call("wait", 3)
        control.call("mouse", "right", "click")
        control.call("wait", 3)
        placed = control.call("block", *ITEM_SAW)["state"]
        if "create:mechanical_saw[" not in placed or "facing=up" not in placed or "axis_along_first=true" not in placed:
            raise RuntimeError(f"The player's vertical saw did not align to its neighboring shaft: {placed}")
        selected_filter = "minecraft:bamboo_mosaic"
        control.call("select", selected_filter)
        filter_x = 8.5 + (-3 if "flipped=true" in placed else 3) / 16
        control.call("look-at", filter_x, 180.75, 8.5)
        control.call("wait", 3)
        control.call("mouse", "right", "click")
        control.call("wait", 3)
        filter_id = control.command(f"/data get block {xyz(ITEM_SAW)} Filter.id")
        if selected_filter not in filter_id or control.call("inventory")["counts"].get(selected_filter) != 2:
            raise RuntimeError(f"Setting the saw's filter returned {filter_id}")
        control.command("/tp @s 12.5 180 12.5")
        control.call("select", "create:mechanical_saw")
        control.call("look-at", 10.0, 180.5, 12.5)
        control.call("wait", 3)
        control.call("mouse", "right", "click")
        control.call("wait", 3)
        placed = control.call("block", 10, 180, 12)["state"]
        if "create:mechanical_saw[" not in placed or "facing=east" not in placed:
            raise RuntimeError(f"The player's horizontal saw did not face east: {placed}")
    print("Normal placement aligned both saws and setting the result filter preserved the held items.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda name: Path(name).resolve(strict=True))
    parser.add_argument("--pack", type=lambda name: Path(name).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--configure", action="store_true")
    parser.add_argument("--runtime", action="store_true")
    args = parser.parse_args()
    (configure if args.configure else run)(args)
