#!/usr/bin/env python3
"""Compare the original stationary Mechanical Drill's progress and drops."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

DRILL = (8, 180, 40)
FRONT = (9, 180, 40)
FIELDS = ("rpm", "progress", "next_tick", "target", "cobblestone", "dirt", "planks")
ACTIONS = {
    3: ("/setblock 9 180 40 minecraft:stone",),
    8: ("/setblock 8 180 39 minecraft:smooth_stone",),
    31: ("/setblock 9 180 40 minecraft:dirt",),
    47: ("/setblock 9 180 40 minecraft:bedrock",),
    53: ("/setblock 9 180 40 minecraft:oak_planks", "/data merge block 7 180 40 {ScrollValue:0}"),
    56: ("/data merge block 7 180 40 {ScrollValue:96}",),
}


def setup(control):
    commands = (
        "/fill 5 179 36 14 179 45 minecraft:smooth_stone",
        "/setblock 8 180 40 create:mechanical_drill[facing=east]",
        "/setblock 7 180 40 create:creative_motor[facing=east]{ScrollValue:96}",
        "/tp @s 12.5 180 41.5",
    )
    for command, reply in zip(commands, control.commands(commands), strict=True):
        if command.startswith("/setblock ") and "Changed the block" not in reply:
            raise RuntimeError(f"Setup failed for {command}: {reply}")
    for _ in range(2):
        control.step_to(control.clock() + 1)


def number(reply):
    value = re.search(r"(-?\d+(?:\.\d+)?)[bfsdL]?$", reply)
    if value is None:
        raise RuntimeError(f"Could not read the drill: {reply}")
    return float(value[1])


def drops(item):
    return (f'/execute if entity @e[type=minecraft:item,x=5,y=179,z=36,dx=9,dy=4,dz=9,'
            f'nbt={{Item:{{id:"minecraft:{item}"}}}}]')


def sample(control):
    positions = " ".join(map(str, DRILL))
    replies = control.commands((
        *(f"/data get block {positions} {field}" for field in ("Speed", "Progress", "NextTick")),
        *(drops(item) for item in ("cobblestone", "dirt", "oak_planks")),
    ))
    return (
        f"{number(replies[0]):.2f}",
        *(str(int(number(reply))) for reply in replies[1:3]),
        control.call("block", *FRONT)["block"],
        *(str(int(number(reply))) if "Test passed" in reply else "0" for reply in replies[3:]),
    )


def run(args):
    with (ROOT / "fixtures/mechanical-drill-java.csv").open() as data:
        expected = tuple(csv.DictReader(data))
    with fixture_world(args, "Mechanical-drill", render=args.visual, pack=args.pack) as control:
        setup(control)
        if args.visual:
            control.call("look-at", 8.5, 180.5, 40.5)
            control.call("key", "f1", "tap")
        start = control.clock()
        differences = []
        with (ROOT / ".local/mechanical-drill-horizon.csv").open("w") as data:
            writer = csv.writer(data)
            writer.writerow(("tick", *FIELDS))
            for row in expected:
                tick = int(row["tick"])
                if tick:
                    control.step_to(start + tick)
                actual = sample(control)
                writer.writerow((tick, *actual))
                for field, value in zip(FIELDS, actual, strict=True):
                    if value != row[field]:
                        differences.append(f"Tick {tick}, {field}: Horizon {value}, Java {row[field]}")
                if differences and not args.diagnostics:
                    raise RuntimeError(differences[-1])
                if args.visual and tick == 0:
                    control.call("screenshot", ROOT / ".local/mechanical-drill.png")
                if args.visual and tick == 26:
                    control.call("screenshot", ROOT / ".local/mechanical-drill-breaking.png")
                if actions := ACTIONS.get(tick):
                    control.commands(actions)
        if differences:
            raise RuntimeError("\n".join(differences[:20]))
    print(f"Mechanical Drill speed, progress, targets and real drops matched {len(expected)} Java ticks.")


def configure(args):
    with fixture_world(args, "Mechanical-drill-placement", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 5 179 36 14 179 45 minecraft:smooth_stone",
            "/setblock 7 180 40 create:shaft[axis=x]",
            "/setblock 13 180 44 minecraft:water",
            "/item replace entity @s hotbar.0 with create:mechanical_drill 2",
        ))
        control.call("select", "create:mechanical_drill")
        for pos, expected in (
            (DRILL, ("facing=east", "waterlogged=false")),
            ((13, 180, 44), ("facing=up", "waterlogged=true")),
        ):
            x, y, z = pos
            control.command(f"/tp @s {x + .5} {y + 2} {z + .5}")
            control.call("look-at", x + .5, y, z + .5)
            control.call("wait", 3)
            control.call("mouse", "right", "click")
            control.call("wait", 3)
            found = control.call("block", *pos)["state"]
            if not found.startswith("create:mechanical_drill[") or any(
                field not in found for field in expected
            ):
                raise RuntimeError(f"Player placement at {pos} gave {found}, expected {expected}")
    print("Player placement used the neighboring shaft and preserved source water around the drill.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda name: Path(name).resolve(strict=True))
    parser.add_argument("--pack", type=lambda name: Path(name).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--configure", action="store_true")
    args = parser.parse_args()
    (configure if args.configure else run)(args)
