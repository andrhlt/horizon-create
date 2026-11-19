#!/usr/bin/env python3
"""Connect a belt in Horizon and replay Java's reversal and depot handoff."""

import argparse
import csv
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/processing/wheat_milling.nbt")
START = "5 104 -11"
MOTOR = "5 104 -12"
DEPOT = "9 104 -11"


def motor_speed(control, speed):
    control.command(f"/data merge block {MOTOR} {{ScrollValue:{speed}}}")


def connect(control):
    control.commands((
        "/fill 3 103 -15 12 103 -6 minecraft:smooth_stone",
        f"/setblock {START} create:shaft[axis=z]",
        "/setblock 8 104 -11 create:shaft[axis=z]",
        "/give @s create:belt_connector",
    ))
    control.call("tp", 6.5, 104, -8.5)
    control.call("select", "create:belt_connector")
    for _ in range(3):
        if "create:belt_connector" in control.command("/data get entity @s SelectedItem"):
            break
        control.call("wait", 1)
    else:
        raise RuntimeError("The server did not equip the connector")
    for _ in range(2):
        control.call("interact", 5, 104, -11)
        if "CreateBeltFirstShaft" in control.command("/data get entity @s SelectedItem"):
            break
    else:
        raise RuntimeError("The first shaft was never selected")

    for _ in range(5):
        control.step_to(control.clock() + 1)
    control.call("interact", 8, 104, -11)
    for x, part in ((5, "start"), (6, "middle"), (7, "middle"), (8, "end")):
        info = control.call("block", x, 104, -11)
        if not info["state"].startswith("create:belt[") or f"part={part}" not in info["state"]:
            raise RuntimeError(f"Connector did not place the {part} at x={x}: {info}")


def sample(control, tick):
    belt, depot = control.commands((f"/data get block {START}", f"/data get block {DEPOT}"))
    speed = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)", belt)
    if not speed or "create:depot" not in depot:
        raise RuntimeError(f"Cannot read belt or depot: {belt}, {depot}")
    positions = {"iron": -1.0, "gold": -1.0}
    for carried in re.findall(r"\{([^{}]*\{[^{}]*\}[^{}]*)\}", belt):
        item = re.search(r'\bid: "minecraft:(iron|gold)_ingot"', carried)
        pos = re.search(r"\bPos: (-?\d+(?:\.\d+)?)", carried)
        if item and pos:
            positions[item[1]] = float(pos[1])
    # The Java fixture inserts one of each ingot and keeps the depot output single-stack.
    return [str(tick), str(int(float(speed[1]))),
            *(f"{positions[item]:.7f}" for item in ("iron", "gold")),
            *(str(int(f'"minecraft:{item}_ingot"' in depot)) for item in ("iron", "gold"))]


def run(args):
    with (ROOT / "fixtures/horizontal_belt-java.csv").open() as file:
        rows = csv.reader(file)
        header, expected = next(rows), list(rows)
    actual = []
    with fixture_world(args, "Horizontal-belt", STRUCTURE, render=True) as control:
        connect(control)
        control.command(f"/setblock {MOTOR} create:creative_motor[facing=south]")
        motor_speed(control, -48)
        control.command(f"/setblock {DEPOT} create:depot")
        control.step_to(control.clock() + 1)
        control.command(
            f'/data merge block {START} {{Inventory:{{PositiveOrder:1b,Items:['
            '{Item:{id:"minecraft:iron_ingot",count:1},PrevPos:0.4375f,Pos:0.4375f,Angle:180},'
            '{Item:{id:"minecraft:gold_ingot",count:1},PrevPos:1.7375f,Pos:1.7375f,Angle:180}]}}'
        )
        start = control.clock()
        for tick in range(len(expected)):
            if tick:
                control.step_to(start + tick)
            actual.append(sample(control, tick))
            if tick in (17, 25):
                motor_speed(control, 48 if tick == 17 else -48)
            if tick == 53:
                control.command(f"/item replace block {DEPOT} container.0 with minecraft:air")
            if tick == 8:
                control.command("/time set noon")
                control.call("look-at", 7, 104.6, -10.2)
                control.call("key", "f1", "tap")
                control.call("wait", 4)
                control.call("screenshot", ROOT / ".local/horizontal_belt.png")
    path = ROOT / ".local/horizontal_belt-horizon.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    differences = [
        (a, b) for a, b in zip(expected, actual, strict=True)
        if a[:2] != b[:2] or a[4:] != b[4:] or
        any(abs(float(a[i]) - float(b[i])) > 0.000001 for i in (2, 3))
    ]
    if differences:
        raise SystemExit(f"Belt differs on {len(differences)} ticks. "
                         f"First rows (Java, Horizon): {differences[:5]}. See {path}")
    print(f"Horizontal belt matched {len(actual)} Java ticks. See {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())


if __name__ == "__main__":
    main()
