#!/usr/bin/env python3
"""Compare motor placement facing toward shafts and with ordinary player aim."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

MOTOR = "create:creative_motor"
SHAFT = "create:shaft"


def place(control, case):
    x, y, z = 8 + case * 5, 101, -10
    control.commands((
        f"/fill {x - 4} {y - 1} {z - 4} {x + 4} {y - 1} {z + 4} minecraft:smooth_stone",
        f"/fill {x - 2} {y} {z - 2} {x + 2} {y + 1} {z + 2} minecraft:air",
        f"/item replace entity @s hotbar.0 with {MOTOR} 2",
    ))
    if case >= 3:
        control.command(f"/setblock {x + 1} {y} {z} {SHAFT}[axis=x]")
    if case == 5:
        control.command(f"/setblock {x} {y} {z - 1} {SHAFT}[axis=z]")
    if case == 6:
        control.command(f"/setblock {x - 1} {y} {z} {SHAFT}[axis=x]")
    if case == 1:
        feet = (x + 3.65, y, z + 0.5)
    elif case in (2, 5):
        feet = (x + 0.5, y, z + 1.45)
    else:
        feet = (x + 0.5, y, z - 2.55)
    control.command("/tp @s " + " ".join(f"{coord:.3f}" for coord in feet))
    control.call("wait", 3)
    control.call("select", MOTOR)
    if case == 4:
        control.call("key", "shift", "down")
        control.call("wait", 3)
    control.call("look-at", x + 0.5, y - 0.001, z + 0.5)
    control.call("wait", 2)
    control.call("mouse", "right", "down")
    control.call("wait", 1)
    control.call("mouse", "right", "up")
    if case == 4:
        control.call("key", "shift", "up")
    control.call("wait", 3)

    state = control.call("block", x, y, z)["state"]
    facing = re.search(r"\bfacing=([a-z]+)\b", state)[1] if state.startswith(MOTOR) else "none"
    return (str(case), facing, str(control.call("inventory")["counts"].get(MOTOR, 0)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    with (ROOT / "fixtures/creative-motor-placement-java.csv").open() as stream:
        _, *rows = list(csv.reader(stream))
    with fixture_world(args, "CreativeMotorPlacement", render=True, pack=args.pack) as control:
        control.command("/gamemode survival")
        actual = [place(control, int(row[0])) for row in rows]
    expected = list(map(tuple, rows))
    if actual != expected:
        differences = [f"case {want[0]} Java {want[1:]}, Horizon {got[1:]}"
                       for want, got in zip(expected, actual, strict=True) if want != got]
        raise RuntimeError("Motor placement mismatch. " + "; ".join(differences))
    print("All seven Java Creative Motor placement cases matched facing and held item use.")


if __name__ == "__main__":
    main()
