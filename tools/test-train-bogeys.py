#!/usr/bin/env python3
"""Use the station assembly screen and compare bogey placement against Java."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/misc/threshold_switch_pulley.nbt")
TRACK = (9, 112, -8)
STATION = (9, 112, -6)


def click_track(control, x, y, z):
    control.call("look-at", x + 0.5, y + 0.06, z + 0.5)
    control.call("mouse", "right", "click")
    control.call("wait", 3)


def setup(control):
    x, y, z = TRACK
    control.commands((
        f"/fill 2 {y - 1} -13 24 {y - 1} -3 minecraft:smooth_stone",
        f"/fill {x - 3} {y} {z} {x + 14} {y} {z} create:track[shape=xo]",
        "/gamemode survival",
        f"/tp @s {x + 2.5} {y} {z + 0.5} 90 20",
        "/item replace entity @s hotbar.0 with create:track_station",
    ))
    control.call("wait", 3)
    control.call("key", "1", "tap")
    click_track(control, *TRACK)
    sx, sy, sz = STATION
    control.command(f"/tp @s {sx + 0.5} {sy} {sz + 2.5} 180 20")
    control.call("wait", 3)
    control.call("interact", sx, sy - 1, sz, "up")
    control.step_to(control.clock() + 1)
    control.call("wait", 3)
    control.call("interact", sx, sy, sz, "up")
    control.call("wait", 5)
    control.call("click-button", "Create New Train")
    control.step_to(control.clock() + 1)
    control.call("wait", 3)
    if "assembling=true" not in control.call("block", *STATION)["state"]:
        raise RuntimeError("The Create New Train button did not enter assembly mode.")
    control.call("key", "esc", "tap")
    control.call("wait", 2)
    control.command("/item replace entity @s hotbar.0 with create:railway_casing 3")
    control.call("wait", 2)


def run(args):
    with (ROOT / "fixtures/train_bogeys-java.csv").open() as expected:
        cases = list(csv.DictReader(expected))
    with fixture_world(args, "Train-bogeys", STRUCTURE, render=True) as control:
        setup(control)
        x, y, z = TRACK
        for case in cases:
            if case["case"] == "5":
                control.command("/item replace entity @s hotbar.0 with minecraft:air")
            # Invalid bogey spots are clicked with an empty hand so the casing
            # item does not perform its normal block placement after the station passes.
            control.call("key", "1" if case["accepted"] == "1" else "2", "tap")
            at = x + int(case["track_distance"])
            control.command(f"/tp @s {at + 0.5} {y} {z - 1.6} 0 20")
            control.call("wait", 2)
            click_track(control, at, y, z)
            found = control.call("blocks", x + 1, y + 1, z, x + 7, y + 1, z)["blocks"]
            actual = {bx: state.split("[")[0].replace(":", ".") for bx, _, _, state in found}
            states = tuple("block." + actual.get(bx, "minecraft.air") for bx in range(x + 1, x + 8))
            if states != tuple(case["bogeys"].split(";")):
                raise RuntimeError(f"Case {case['case']} had {states}, Java {case['bogeys']}")
            player = control.command("/data get entity @s Inventory")
            remaining = sum(int(re.search(r"count: (\d+)", slot)[1]) for slot in player.split('}, {')
                            if 'id: "create:railway_casing"' in slot)
            if remaining != int(case["supply"]):
                raise RuntimeError(f"Case {case['case']} expected {case['supply']} Train Casing, read {remaining}")
        if args.visual:
            control.command("/time set noon")
            control.command(f"/tp @s {x + 3.5} {y + 5} {z - 2.5} 30 35")
            control.call("look-at", x + 3.0, y + 0.5, z + 0.5)
            control.call("key", "f1", "tap")
            control.call("wait", 5)
            control.call("screenshot", ROOT / ".local/train-bogeys.png")
    print(f"All {len(cases)} station assembly and bogey cases matched Java.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
