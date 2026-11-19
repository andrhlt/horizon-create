#!/usr/bin/env python3
"""Replay the original Java Create mounted arrow dispenser GameTest."""
import argparse
import csv
from pathlib import Path
import re
import struct

from fixture_world import ROOT, fixture_world

TEMPLATE = Path("gametest/contraptions/arrow_dispenser.nbt")
ORIGIN = (3, 96, -12)
VECTOR = re.compile(r"\[(-?[\d.Ee+-]+)d, (-?[\d.Ee+-]+)d, (-?[\d.Ee+-]+)d\]")
ARROWS = "@e[type=minecraft:arrow,x=3,y=100,z=-12,dx=4,dy=0,dz=4]"


def value(reply):
    return reply.partition(" has the following block data: ")[2]


def direction(replies):
    motions = [tuple(map(float, match.groups())) for reply in replies
               if (match := VECTOR.search(reply))]
    moving = [motion for motion in motions if motion != (0.0, 0.0, 0.0)]
    if len(moving) != 1:
        raise RuntimeError(f"Expected one newly launched arrow. Found motions {motions}.")
    x, _, z = moving[0]
    if abs(x) > abs(z):
        return "east" if x > 0 else "west"
    return "south" if z > 0 else "north"


def sample(control, tick, start, previous_count):
    running, angle, in_block, mounted, arrows, display = control.commands((
        "/data get block 5 99 -10 Running",
        "/data get block 5 99 -10 Angle",
        "/data get block 5 100 -10 Items",
        "/data get block 5 99 -10 MovedBlocks[0].VanillaEntity.Items",
        f"/execute if entity {ARROWS}",
        "/data get entity @e[type=minecraft:block_display,limit=1] Pos",
    ))
    count = int(match[1]) if (match := re.search(r"Count: (\d+)", arrows)) else int("Test passed" in arrows)
    launch = ""
    if count > previous_count:
        arrows = control.call("command", f"/execute as {ARROWS} run data get entity @s Motion")["chat"]
        launch = direction(arrows)
    geometry = ""
    source = in_block
    if value(running) == "1b":
        native_angle, = struct.unpack("f", struct.pack("f", float(value(angle).removesuffix("f"))))
        position = VECTOR.search(display)
        if not position:
            raise RuntimeError(f"The moving dispenser has no visible payload. {display}")
        relative = (f"{float(value) - base:.9f}" for value, base in zip(position.groups(), ORIGIN, strict=True))
        geometry = ":".join((*relative, f"{native_angle:.6f}"))
        source = mounted
    ammo = sum(map(int, re.findall(r"\bcount: (\d+)", value(source))))
    return [str(tick), str((start + tick) % 20), geometry, str(ammo), str(count), launch]


def run(args):
    with (ROOT / "fixtures/arrow_dispenser-java.csv").open() as reference:
        rows = csv.reader(reference)
        header, expected = next(rows), list(rows)[:args.ticks]
    actual = []
    with fixture_world(args, "arrow-dispenser", TEMPLATE) as control:
        while control.clock() % 20 != int(expected[0][1]):
            control.step_to(control.clock() + 1)
        lever = "/setblock 5 98 -11 minecraft:lever[face=wall,facing=north,powered="
        control.commands((
            "/place template create:gametest/contraptions/arrow_dispenser 3 96 -12",
            lever + "false]",
        ))
        start = control.clock()
        count = 0
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            current = sample(control, tick, start, count)
            count = int(current[4])
            actual.append(current)
            if tick >= 140 and count == 4:
                control.command(lever + "true]")
    path = ROOT / ".local/arrow_dispenser-horizon.csv"
    with path.open("w", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    if differences:
        raise SystemExit(f"Arrow dispenser differed at {len(differences)} ticks (Java, Horizon): {differences[:6]}.")
    print(f"Arrow dispenser matched all {len(actual)} Java ticks. See {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args()
    if args.ticks is not None and args.ticks < 1:
        parser.error("--ticks must be positive")
    run(args)
