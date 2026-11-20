#!/usr/bin/env python3
"""Compare the signed controller settings and both drive directions with Java."""

import argparse
import csv
from math import isclose
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

ABOVE = (6, 101, -10)
FROM_SHAFT = (14, 101, -10)
UPPER_INPUT = (6, 102, -10)
SHAFT_OUTPUT = (6, 101, -9)
UPPER_OUTPUT = (14, 102, -10)
COG_SHAFT_OUTPUT = (15, 102, -10)
SHAFT_THROUGH = (14, 101, -9)
GEAR_MOTOR = (5, 102, -10)
SETTINGS = {4: (1, 64), 12: (0, 32), 21: (1, 0), 28: (1, 256), 45: (1, 12)}
BOUNDARY_SETTINGS = {3: (0, 0), 6: (0, 73), 12: (0, 256), 15: (1, 256), 21: (1, 23)}
ZERO_TARGET_TICKS = {9, 18}


def coords(pos):
    return " ".join(map(str, pos))


def setup(control, *, loaded=False):
    control.commands((
        "/fill 3 100 -13 17 100 -6 minecraft:smooth_stone",
        "/fill 3 101 -13 17 104 -6 minecraft:air",
        *(f"/setblock {coords(pos)} create:rotation_speed_controller[axis=z]" for pos in (ABOVE, FROM_SHAFT)),
        *(f"/setblock {coords(pos)} create:large_cogwheel[axis=x]" for pos in (UPPER_INPUT, UPPER_OUTPUT)),
        *(f"/setblock {coords(pos)} create:shaft[axis=z]" for pos in (SHAFT_OUTPUT, SHAFT_THROUGH)),
        f"/setblock {coords(COG_SHAFT_OUTPUT)} create:shaft[axis=x]",
        f"/setblock {coords(GEAR_MOTOR)} create:creative_motor[facing=east]",
        "/setblock 14 101 -11 create:creative_motor[facing=south]",
        f"/data merge block {coords(GEAR_MOTOR)} {{ScrollValue:24}}",
        "/data merge block 14 101 -11 {ScrollValue:24}",
        "/tp @s 3.75 101 -9.5",
        "/gamemode survival",
    ))
    if loaded:
        control.commands((
            "/setblock 6 101 -8 create:encased_fan[facing=south]",
            "/setblock 7 102 -10 create:encased_fan[facing=east]",
            "/setblock 14 101 -8 create:encased_fan[facing=south]",
            "/setblock 16 102 -10 create:encased_fan[facing=east]",
        ))



def tag(text, key, kind):
    pattern = rf"\b{key}: (-?\d+(?:\.\d+)?)" + ("f" if kind is float else "") + r"\b"
    match = re.search(pattern, text)
    if match is None:
        raise RuntimeError(f"Missing {key} in {text}.")
    return kind(match[1])


def sample(control, *, loaded=False):
    above, shaft, upper_input, shaft_output, upper_output, cog_output, through = control.commands(
        f"/data get block {coords(pos)}" for pos in (
            ABOVE, FROM_SHAFT, UPPER_INPUT, SHAFT_OUTPUT, UPPER_OUTPUT, COG_SHAFT_OUTPUT, SHAFT_THROUGH,
        )
    )
    values = (
        tag(above, "ScrollValue", int), tag(shaft, "ScrollValue", int),
        *(tag(nbt, "Speed", float) for nbt in (upper_input, above, shaft_output, shaft, upper_output, cog_output, through)),
    )
    if loaded:
        values += tuple(tag(nbt, key, float) for nbt in (above, shaft)
                        for key in ("Stress", "Capacity"))
    return values


def configure(control, pos, row, column, *, check_press=False, axis="z"):
    x, y, z = pos
    if axis == "x":
        control.command(f"/tp @s {x + 0.5} {y} {z - 2.0}")
    else:
        control.command(f"/tp @s {x - 2.0} {y} {z + 0.5}")
    control.call("wait", 3)
    choose_setting(control, pos, row, column, check_press=check_press, axis=axis)


def choose_setting(control, pos, row, column, *, check_press=False, axis="z"):
    x, y, z = pos
    if axis == "x":
        control.call("look-at", x + 0.5, y + 0.6875, z + 0.03)
    else:
        control.call("look-at", x + 0.03, y + 0.6875, z + 0.5)
    control.call("mouse", "right", "down")
    control.call("wait", 7)

    label = "Counterclockwise RPM" if row == 0 else "Clockwise RPM"
    buttons = control.call("screen")["buttons"]
    cell = next((button for button in buttons if button["label"] == label), None)
    if cell is None:
        raise RuntimeError(f"The controller board did not open after holding use: {buttons}.")
    offset = ((max(1, column) - 1) // 32) * 4 + column + 1.5
    if column % 32 == 0:
        offset += 2
    if column > 0:
        offset += 4
    x = cell["x"] + offset
    y = cell["y"] + cell["h"] / 2
    control.call("scroll-at", x, y, 0)
    if check_press:
        command = f"/data get block {coords(pos)} ScrollValue"
        previous = control.command(command)
        control.call("click-at", x, y)
        control.call("wait", 2)
        if control.command(command) != previous or control.call("state")["screen"] != "mod":
            raise RuntimeError("A click other than use release changed the controller board.")
    control.call("click-at", x, y, "right")
    control.call("wait", 3)
    if control.call("state")["screen"] != "playing":
        raise RuntimeError("Releasing use did not close the controller board.")


def verify_short_press(control):
    control.call("wait", 3)
    x, y, z = ABOVE
    control.call("look-at", x + 0.03, y + 0.6875, z + 0.5)
    control.call("script", script="mouse right down\nwait 3\nmouse right up\nwait 4\n")
    if control.call("state")["screen"] != "playing":
        raise RuntimeError("The controller board opened before six held client ticks.")


def verify_input_trace(log):
    held = {}
    opened = 0
    releases = 0
    submits = 0
    for line in log.read_text().splitlines():
        if not line.startswith("CREATE_SPEED_CONTROLLER_INPUT "):
            continue
        _, tick, event, pos = line.split()
        tick = int(tick)
        if event == "hold":
            held[pos] = tick
        elif event == "open":
            elapsed = tick - held[pos] + 1
            if elapsed != 6:
                raise RuntimeError(f"The controller board opened after {elapsed} held client ticks.")
            opened += 1
        elif event == "release":
            releases += 1
        elif event == "submit":
            if releases <= submits:
                raise RuntimeError("The controller sent a setting before use release.")
            submits += 1
    if (opened, releases, submits) != (10, 10, 10):
        raise RuntimeError(f"Expected ten held selections, got {opened} opens, {releases} releases, and {submits} submits.")


def verify(args):
    stem = "rotation-speed-controller"
    settings = SETTINGS
    if args.boundaries:
        stem += "-boundaries"
        settings = BOUNDARY_SETTINGS
    elif args.loaded:
        stem += "-loaded"
    with (ROOT / f"fixtures/{stem}-java.csv").open() as data:
        header, *expected = list(csv.reader(data))
    actual = []
    differences = []
    trace_env = {"CREATE_SPEED_CONTROLLER_INPUT_TRACE": "1"}
    with fixture_world(args, stem, render=True, pack=args.pack, env=trace_env) as control:
        setup(control, loaded=args.loaded)
        verify_short_press(control)
        start = control.clock()
        for row in expected[1:]:
            tick = int(row[0])
            control.step_to(start + tick)
            values = sample(control, loaded=args.loaded)
            actual.append((tick, *values))
            for key, wanted, got in zip(header[1:], row[1:], values, strict=True):
                if not isclose(float(wanted), got, abs_tol=0.00005, rel_tol=0.0):
                    differences.append((tick, key, wanted, got))
            if selection := settings.get(tick):
                for pos in (ABOVE, FROM_SHAFT):
                    configure(control, pos, *selection, check_press=tick == 4 and pos == ABOVE)
            if args.boundaries and tick in ZERO_TARGET_TICKS:
                control.commands(
                    f"/data merge block {coords(pos)} {{ScrollValue:0}}" for pos in (ABOVE, FROM_SHAFT)
                )
            if not args.boundaries and tick == 36:
                control.command(f"/data merge block {coords(GEAR_MOTOR)} {{ScrollValue:40}}")
        verify_input_trace(control.socket.parent / "ctl.log")
    output = args.output or ROOT / f".local/{stem}-horizon.csv"
    with output.open("w") as data:
        writer = csv.writer(data)
        writer.writerow(header)
        writer.writerows(actual)
    if differences:
        raise RuntimeError(f"{len(differences)} controller mismatches. First 20: {differences[:20]}")
    print(f"Both speed controller drive directions matched Java for {len(actual)} simulated ticks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--loaded", action="store_true")
    mode.add_argument("--boundaries", action="store_true")
    parser.add_argument("--output", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
