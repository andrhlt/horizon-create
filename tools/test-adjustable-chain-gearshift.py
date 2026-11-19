#!/usr/bin/env python3
"""Replay the adjustable chain gearshift at both ends of a powered chain."""

import argparse
import csv
from math import isclose
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

FORWARD = (6, 101, -10)
REVERSE = (11, 101, -10)
FORWARD_OUTPUT = (7, 102, -10)
REVERSE_OUTPUT = (11, 102, -10)
LEVERS = ((6, 101, -9), (11, 101, -9))


def coords(pos):
    return " ".join(map(str, pos))


def block_data(control, pos):
    return control.command(f"/data get block {coords(pos)}")


def value(nbt, field, kind):
    match = re.search(rf"\b{field}: (-?\d+(?:\.\d+)?)" + ("f" if kind is float else "") + r"\b", nbt)
    if match is None:
        raise RuntimeError(f"Missing {field} in {nbt}")
    return kind(match[1])


def setup(control):
    control.commands((
        "/fill 4 100 -12 14 100 -7 minecraft:smooth_stone",
        "/fill 4 101 -12 14 103 -7 minecraft:air",
        "/setblock 6 101 -10 create:adjustable_chain_gearshift[axis=y,part=start,axis_along_first=true]",
        "/setblock 7 101 -10 create:encased_chain_drive[axis=y,part=end,axis_along_first=true]",
        "/setblock 11 101 -10 create:adjustable_chain_gearshift[axis=y,part=start,axis_along_first=true]",
        "/setblock 12 101 -10 create:encased_chain_drive[axis=y,part=end,axis_along_first=true]",
        *(f"/setblock {x} 102 -10 create:shaft[axis=y]" for x in (6, 7, 11, 12)),
        *(f"/setblock {x} 100 -10 create:creative_motor[facing=up]" for x in (6, 12)),
        *(f"/data merge block {x} 100 -10 {{ScrollValue:24}}" for x in (6, 12)),
        *(f"/setblock {coords(pos)} create:analog_lever[face=floor,facing=south]" for pos in LEVERS),
        "/tp @s 5.5 101 -8.5",
        "/gamemode survival",
    ))


def sample(control, tick):
    first, first_output, last, last_output = control.commands(
        f"/data get block {coords(pos)}" for pos in (FORWARD, FORWARD_OUTPUT, REVERSE, REVERSE_OUTPUT)
    )
    state = lambda pos: control.call("block", *pos)["state"]
    signal = lambda nbt: value(nbt, "Signal", int)
    modifier = lambda n: 1.0 + ((n + 1) / 16.0 if n else 0.0)
    rpm = lambda nbt: value(nbt, "Speed", float)
    return (
        0 if tick > 70 else value(block_data(control, LEVERS[0]), "State", int),
        str("powered=true" in state(FORWARD)).lower(),
        str("powered=true" in state(REVERSE)).lower(),
        modifier(signal(first)),
        modifier(signal(last)),
        rpm(first),
        rpm(first_output),
        rpm(last),
        rpm(last_output),
    )


def press(control, count):
    for lever in LEVERS:
        control.command(f"/tp @s {lever[0] - 0.5} 101 -8.5")
        control.call("wait", 4)
        if count < 0:
            control.call("key", "shift", "down")
            control.call("wait", 3)
            control.call("look-at", lever[0] + 0.5, lever[1] + 0.17, lever[2] + 0.5)
        try:
            for _ in range(abs(count)):
                if count < 0:
                    control.call("mouse", "right", "click")
                else:
                    control.call("interact", *lever)
                control.call("wait", 4)
        finally:
            if count < 0:
                control.call("key", "shift", "up")


def verify_placement(control):
    control.commands((
        "/fill 5 101 -11 8 103 -8 minecraft:air",
        "/setblock 6 100 -10 create:shaft[axis=y]",
        "/setblock 7 100 -10 create:shaft[axis=y]",
        "/tp @s 5.5 101 -8.5",
        "/gamemode creative",
        "/item replace entity @s hotbar.0 with create:adjustable_chain_gearshift",
        "/item replace entity @s hotbar.1 with create:encased_chain_drive",
    ))
    control.step_to(control.clock() + 1)
    control.call("wait", 4)
    control.call("select", "create:adjustable_chain_gearshift")
    control.call("interact", 6, 100, -10, "up")
    initial = control.call("block", *FORWARD)["state"]
    if "axis=y" not in initial or "part=none" not in initial:
        raise RuntimeError(f"Expected an unattached vertical gearshift, got {initial}.")
    control.command("/tp @s 8.5 101 -8.5")
    control.call("wait", 4)
    control.call("select", "create:encased_chain_drive")
    control.call("interact", 7, 100, -10, "up")
    left, right = (control.call("block", x, 101, -10)["state"] for x in (6, 7))
    if not all(part in left for part in ("axis=y", "axis_along_first=true", "part=start")):
        raise RuntimeError(f"Expected the adjustable drive to link east, got {left}.")
    if not all(part in right for part in ("axis=y", "axis_along_first=true", "part=end")):
        raise RuntimeError(f"Expected the encased drive to link west, got {right}.")
    control.command(f"/setblock {coords(FORWARD)} minecraft:air")
    control.step_to(control.clock() + 1)
    detached = control.call("block", 7, 101, -10)["state"]
    if "part=none" not in detached:
        raise RuntimeError(f"Expected the remaining drive to detach, got {detached}.")


def verify(args):
    with (ROOT / "fixtures/adjustable-chain-gearshift-java.csv").open() as source:
        header, *reference = list(csv.reader(source))
    actual_rows = []
    mismatches = []
    with fixture_world(args, "AdjustableChainGearshift", render=True, pack=args.pack) as control:
        setup(control)
        # Java records row zero after placement and before the first BE tick.
        # Horizon publishes RPM after its first simulated tick.
        start = control.clock()
        for row in reference[1:]:
            tick = int(row[0])
            control.step_to(start + tick)
            actual = sample(control, tick)
            actual_rows.append((tick, *actual))
            for key, target, got in zip(header[1:], row[1:], actual, strict=True):
                matched = target == got if isinstance(got, str) else isclose(
                    float(target), got, abs_tol=0.00005, rel_tol=0.0,
                )
                if not matched:
                    mismatches.append((tick, key, target, got))
            change = {4: 7, 26: 8, 43: -3}.get(tick)
            if change is not None:
                press(control, change)
            if tick == 70:
                control.commands(f"/setblock {coords(pos)} minecraft:air destroy" for pos in LEVERS)
        if not mismatches:
            verify_placement(control)
    with args.output.open("w") as result:
        writer = csv.writer(result)
        writer.writerow(header)
        writer.writerows(actual_rows)
    if mismatches:
        raise RuntimeError(f"{len(mismatches)} chain gearshift mismatches. First 20: {mismatches[:20]}")
    print(f"Adjustable chain gearshift matched Java for {len(actual_rows)} simulated ticks in both directions.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/adjustable-chain-gearshift-horizon.csv")
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
