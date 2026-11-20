#!/usr/bin/env python3
"""Compare the actual Creative Motor board and shaft speeds with pinned Java."""

import argparse
import csv
import importlib.util
from math import isclose
from pathlib import Path

from fixture_world import ROOT, fixture_world


def controller_helpers():
    path = ROOT / "tools/test-rotation-speed-controller.py"
    spec = importlib.util.spec_from_file_location("controller", path)
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    return controller


controller = controller_helpers()
HORIZONTAL = (8, 101, -10)
VERTICAL = (14, 101, -10)
POSITIONS = (HORIZONTAL, (8, 101, -9), VERTICAL, (14, 102, -10))
with (ROOT / "fixtures/creative-motor-hit-java.csv").open() as data:
    SLOT_OFFSETS = {
        (entry["facing"], entry["face"]): tuple(float(entry[k]) for k in "xyz")
        for entry in csv.DictReader(data) if entry["active"] == "true"
    }
SETTINGS = {4: (1, 64), 11: (0, 24), 20: (1, 0), 28: (1, 256), 36: (0, 11)}


def setup(control):
    control.commands((
        "/fill 3 100 -14 16 100 -7 minecraft:smooth_stone",
        "/fill 3 101 -14 16 104 -7 minecraft:air",
        "/setblock 8 101 -10 create:creative_motor[facing=south]",
        "/setblock 8 101 -9 create:shaft[axis=z]",
        "/setblock 14 101 -10 create:creative_motor[facing=up]",
        "/setblock 14 102 -10 create:shaft[axis=y]",
        "/gamemode survival",
    ))


def no_board(control, *, inactive=False):
    x, y, z = HORIZONTAL
    if inactive:
        control.command(f"/tp @s {x + 0.5} {y} {z - 2}")
        target = (x + 0.5, y + 0.5, z + 0.01)
    else:
        control.command(f"/tp @s {x - 2} {y} {z + 0.4375}")
        target = (x + 0.19, y + 0.5, z + 0.4375)
    control.call("wait", 3)
    control.call("look-at", *target)
    control.call("mouse", "right", "down")
    control.call("wait", 8 if inactive else 3)
    if control.call("state")["screen"] != "playing":
        raise RuntimeError(f"The {'inactive side' if inactive else 'short press'} opened the motor board.")
    control.call("mouse", "right", "up")


def configure(control, pos, row, column, *, teleport=True, facing="south"):
    x, y, z = pos
    _, center_y, center_z = SLOT_OFFSETS[facing, "west"]
    if teleport:
        control.command(f"/tp @s {x - 2} {y} {z + center_z}")
        control.call("wait", 3)
    control.call("look-at", x + 0.19, y + center_y, z + center_z)
    control.call("mouse", "right", "down")
    control.call("wait", 7)
    label = "Counterclockwise RPM" if row == 0 else "Clockwise RPM"
    cell = next((button for button in control.call("screen")["buttons"] if button["label"] == label), None)
    if not cell:
        raise RuntimeError(f"No motor board after seven input ticks at {pos}, row {row}.")
    offset = ((max(1, column) - 1) // 32) * 4 + column + 1.5
    if column % 32 == 0:
        offset += 2
    if column > 0:
        offset += 4
    pointer = (cell["x"] + offset, cell["y"] + cell["h"] / 2)
    control.call("scroll-at", *pointer, 0)
    control.call("click-at", *pointer, "right")
    control.call("wait", 3)
    if control.call("state")["screen"] != "playing":
        raise RuntimeError(f"The motor board stayed open after release at {pos}.")


def sample(control):
    first, first_shaft, second, second_shaft = control.commands(
        f"/data get block {controller.coords(pos)}" for pos in POSITIONS
    )
    return (controller.tag(first, "ScrollValue", int), controller.tag(second, "ScrollValue", int),
            *(controller.tag(nbt, "Speed", float) for nbt in (first, first_shaft, second, second_shaft)))


def verify(args, header, rows):
    actual = []
    with fixture_world(args, "CreativeMotorValueSettings", render=True, pack=args.pack,
                       env={"CREATE_SPEED_CONTROLLER_INPUT_TRACE": "1"}) as control:
        setup(control)
        no_board(control, inactive=True)
        no_board(control)
        start = control.clock()
        for row in rows:
            tick = int(row[0])
            control.step_to(start + tick)
            got = (tick, *sample(control))
            actual.append(got)
            for column, want, value in zip(header, row, got, strict=True):
                if not isclose(float(want), value, abs_tol=0.00001, rel_tol=0.0):
                    raise RuntimeError(f"Tick {tick} {column}. Java {want}. Horizon {value}.")
            if tick in SETTINGS:
                for motor in (HORIZONTAL, VERTICAL):
                    configure(control, motor, *SETTINGS[tick])
        controller.verify_input_trace(control.socket.parent / "ctl.log")

    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    print(f"Both motor settings and their driven shafts matched Java during all {len(actual)} simulated ticks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/creative-motor-horizon.csv")
    args = parser.parse_args()
    with (ROOT / "fixtures/creative-motor-java.csv").open() as stream:
        header, _, *rows = list(csv.reader(stream))
    verify(args, header, rows)


if __name__ == "__main__":
    main()
