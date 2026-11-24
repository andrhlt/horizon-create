#!/usr/bin/env python3
"""Check Crushing Wheel axis choice, survival layout, and controller formation."""

import argparse
from pathlib import Path

from fixture_world import fixture_world

WHEEL = "create:crushing_wheel"
CONTROLLER = "create:crushing_wheel_controller"


def place_wheel(control, target, support, *, sneaking=False):
    control.command(f"/tp @s {target[0] - 1.7} {target[1]} {target[2] + 0.5}")
    control.call("look", -90, 0)
    control.call("select", WHEEL)
    if sneaking:
        control.call("key", "shift", "down")
    control.call("wait", 3)
    try:
        control.call("interact", *support, "north")
    finally:
        if sneaking:
            control.call("key", "shift", "up")
    control.call("wait", 2)
    return control.call("block", *target)["state"]


def run(args):
    with fixture_world(args, "CrushingWheelPlacement", render=True, pack=args.pack) as control:
        control.command("/gamemode survival")
        control.command("/fill 5 100 5 32 100 14 minecraft:smooth_stone")

        valid_target = (10, 101, 10)
        valid_support = (10, 101, 11)
        control.command(f"/setblock {' '.join(map(str, valid_support))} minecraft:stone")
        control.command("/setblock 11 101 10 create:shaft[axis=x]")
        control.command(f"/item replace entity @s hotbar.0 with {WHEEL} 3")
        valid_state = place_wheel(control, valid_target, valid_support)
        if not valid_state.startswith(WHEEL) or "axis=x" not in valid_state:
            raise RuntimeError(f"Expected shaft-aligned survival placement on X, got {valid_state}")
        if control.call("inventory")["counts"].get(WHEEL) != 2:
            raise RuntimeError("Valid wheel placement did not consume exactly one wheel")

        sneaking_target = (14, 101, 10)
        sneaking_support = (14, 101, 11)
        control.command(f"/setblock {' '.join(map(str, sneaking_support))} minecraft:stone")
        control.command("/setblock 15 101 10 create:shaft[axis=x]")
        sneaking_state = place_wheel(control, sneaking_target, sneaking_support, sneaking=True)
        if not sneaking_state.startswith(WHEEL) or "axis=z" not in sneaking_state:
            raise RuntimeError(f"Sneaking did not override the preferred shaft axis, got {sneaking_state}")
        if control.call("inventory")["counts"].get(WHEEL) != 1:
            raise RuntimeError("Sneaking wheel placement did not consume exactly one wheel")

        invalid_target = (18, 101, 10)
        invalid_support = (18, 101, 11)
        control.command(f"/setblock {' '.join(map(str, invalid_support))} minecraft:stone")
        control.command(f"/setblock 19 101 10 {WHEEL}[axis=y]")
        control.call("select", WHEEL)
        invalid_state = place_wheel(control, invalid_target, invalid_support)
        if invalid_state.startswith(WHEEL):
            raise RuntimeError(f"Invalid adjacent wheel layout was accepted: {invalid_state}")
        if control.call("inventory")["counts"].get(WHEEL) != 1:
            raise RuntimeError("Rejected wheel placement consumed the held wheel")

        control.commands((
            f"/setblock 26 101 10 {WHEEL}[axis=x]",
            f"/setblock 26 103 10 {WHEEL}[axis=x]",
        ))
        for _ in range(2):
            control.step_to(control.clock() + 1)
        formed = control.call("block", 26, 102, 10)["state"]
        if not formed.startswith(CONTROLLER):
            raise RuntimeError(f"Aligned wheel pair did not form its controller: {formed}")
    print("Survival wheel placement selected or overrode the shaft axis as expected, rejected an invalid neighboring wheel without consuming it, and aligned wheels formed a controller.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
