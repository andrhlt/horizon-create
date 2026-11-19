#!/usr/bin/env python3
"""Drive an assembled train around a quarter-turn and compare all four wheel positions."""
import argparse
import csv
import importlib.util
import math
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

spec = importlib.util.spec_from_file_location("simple_train", Path(__file__).with_name("test-simple-train.py"))
train = importlib.util.module_from_spec(spec)
spec.loader.exec_module(train)
X, Y, Z = train.X, train.Y, train.Z = 8, 180, 8
train.STATION = (X, Y, Z + 2)
KEYS = ("speed", *(f"wheel_{wheel}_{axis}" for wheel in range(1, 5) for axis in "xyz"))


def layout(control, *, branching=False, mirrored=False, branch_length=20):
    bend = 1 if mirrored else -1
    floor_start, floor_end = sorted((Z + bend * 12, Z - bend * 5))
    branch_start, branch_end = sorted((Z + bend * 46, Z + bend * 13))
    rail_start, rail_end = sorted((Z + bend * 45, Z + bend * 11))
    if mirrored:
        control.command(f"/tp @s {X - 12.5} {Y} {Z + 32.5}")
        control.call("wait", 6)
    control.commands((
        f"/fill {X - 16} {Y - 1} {floor_start} {X + 25} {Y - 1} {floor_end} minecraft:smooth_stone",
        f"/fill {X - 16} {Y - 1} {branch_start} {X - 10} {Y - 1} {branch_end} minecraft:smooth_stone",
        f"/fill {X - 3} {Y} {Z} {X + 24} {Y} {Z} create:track[shape=xo]",
        f"/fill {X - 13} {Y} {rail_start} {X - 13} {Y} {rail_end} create:track[shape=zo]",
        "/gamemode survival",
        f"/tp @s {X - 0.5} {Y} {Z + 0.5} 90 20",
        "/item replace entity @s hotbar.0 with create:track 64",
    ))
    if mirrored:
        for z in (rail_start, rail_end):
            if control.call("block", X - 13, Y, z)["block"] != "create:track":
                raise RuntimeError(f"The mirrored rail corridor was not loaded at {z}.")
    if branching:
        control.commands((
            f"/fill {X - branch_length - 1} {Y - 1} {Z - 4} {X - 16} {Y - 1} {Z + 4} minecraft:smooth_stone",
            f"/fill {X - branch_length} {Y} {Z} {X - 4} {Y} {Z} create:track[shape=xo]",
        ))
    control.call("wait", 3)
    control.call("key", "1", "tap")
    train.click_track(control, X - 3)
    selected = control.command("/data get entity @s Inventory")
    if "create:track_connecting_from" not in selected:
        raise RuntimeError(f"Curve connection start was not selected: {selected}")
    approach = Z + (8.5 if mirrored else -7.5)
    control.command(f"/tp @s {X - 12.5} {Y} {approach} {0 if mirrored else 180} 20")
    control.call("wait", 3)
    control.call("interact", X - 13, Y - 1, Z + bend * 10, "up")
    control.call("wait", 3)
    inventory = control.command("/data get entity @s Inventory")
    if "create:track_connecting_from" in inventory:
        raise RuntimeError(f"Curve connection was not placed: {inventory}")


def place_signals(control, *, branch=False, both_west=False):
    targets = ((X - 2, Z), (X - 2, Z), (X - 13, Z - 15), (X - 13, Z - 15))
    positions = ((X - 2, Z - 3), (X - 2, Z + 3), (X - 10, Z - 15), (X - 16, Z - 15))
    headings = (90, -90, 0, 180)
    approaches = ((2, 0), (-2, 0), (0, -2), (0, 2))
    if branch:
        targets += ((X - 12, Z),)
        positions += ((X - 12, Z + 3),)
        headings += (90,)
        approaches += ((2, 0),)
    if both_west:
        targets += ((X - 12, Z),)
        positions += ((X - 12, Z - 3),)
        headings += (-90,)
        approaches += ((-2, 0),)
    for (x, z), (a, b), heading, (dx, dz) in zip(targets, positions, headings, approaches, strict=True):
        control.commands((
            "/item replace entity @s hotbar.0 with create:track_signal",
            f"/tp @s {x + 0.5 + dx} {Y} {z + 0.5 + dz} {heading} 20",
        ))
        control.call("wait", 3)
        control.call("select", "create:track_signal")
        control.call("look-at", x + 0.5, Y + 0.06, z + 0.5)
        control.call("mouse", "right", "click")
        control.call("wait", 3)
        control.command(f"/tp @s {a + 0.5} {Y} {b + 1.5}")
        control.call("wait", 3)
        control.call("interact", a, Y - 1, b, "up")
        control.call("wait", 3)
        if control.call("block", a, Y, b)["block"] != "create:track_signal":
            raise RuntimeError(f"Could not place a signal at {a} {Y} {b}.")


def signal_lamps(control, *, branch=False, both_west=False):
    positions = ((X - 2, Z - 3), (X - 2, Z + 3), (X - 10, Z - 15), (X - 16, Z - 15))
    if branch:
        positions += ((X - 12, Z + 3),)
    if both_west:
        positions += ((X - 12, Z - 3),)
    return tuple(
        re.search(r'"([A-Z]+)"$', reply)[1]
        for reply in control.commands(f"/data get block {x} {Y} {z} State" for x, z in positions)
    )


def sample(control):
    speed, points = control.commands(
        f"/data get entity {train.ENTITY} CreateTrain.{key}" for key in ("Speed", "WheelPointsXYZ")
    )
    floats = tuple(float(value) for value in re.findall(f"({train.NUMBER})d", points))
    if len(floats) != 12:
        raise RuntimeError(f"Failed to parse four wheel positions from {points}")
    return float(re.search(f"({train.NUMBER})d$", speed)[1]), *floats


def run(args):
    global Z
    fixture = "curved_train"
    lamp_keys = ()
    drive, coast = 18, 92
    branching = args.steer_right or args.steer_left or args.branch_signals
    steering_key = "a" if args.steer_left else "d"
    has_signals = args.signals or args.branch_signals
    if has_signals or branching:
        Z = train.Z = 72
        train.STATION = (X, Y, Z + 2)
        drive, coast = 24, 98
    if args.signals:
        fixture = "curved_signal_occupancy"
        lamp_keys = ("east_in", "east_out", "north_in", "north_out")
    if args.steer_right:
        fixture = "train_steer_right"
    if args.steer_left:
        fixture = "train_steer_left"
    if args.branch_signals:
        fixture = "branched_signal_occupancy"
        lamp_keys = ("east_in", "east_out", "north_in", "north_out", "west_out", "west_in")
    with (ROOT / f"fixtures/{fixture}-java.csv").open() as data:
        expected = tuple(csv.DictReader(data))
    with fixture_world(args, fixture.replace("_", "-"), train.STRUCTURE, render=True, pack=args.pack) as control:
        def signals_after_station(control):
            place_signals(control, branch=args.branch_signals, both_west=args.branch_signals)
        train.setup(control, lambda control: layout(control, branching=branching, mirrored=args.steer_left),
                    after_station=signals_after_station if has_signals else None)
        control.command("/attribute @s minecraft:gravity base set 0")
        start = control.clock()
        first = int(expected[0]["tick"])
        with (ROOT / f".local/{fixture}-horizon.csv").open("w") as log:
            writer = csv.writer(log)
            writer.writerow(("tick", *KEYS, *lamp_keys))
            first_difference = None
            for row in expected:
                tick = int(row["tick"])
                if tick != first:
                    control.step_to(start + tick - first)
                found = sample(control)
                lamps = (
                    signal_lamps(control, branch=args.branch_signals, both_west=args.branch_signals)
                    if has_signals else ()
                )
                writer.writerow((tick, *found, *lamps))
                for key, value in zip(lamp_keys, lamps, strict=True):
                    if value != row[key]:
                        detail = f"Tick {tick} {key}: Horizon {value}, Java {row[key]}"
                        if not args.diagnostics:
                            raise RuntimeError(detail)
                        first_difference = first_difference or detail
                for key, value in zip(KEYS, found, strict=True):
                    if not math.isclose(value, float(row[key]), rel_tol=0.0, abs_tol=args.tolerance):
                        detail = f"Tick {tick} {key}: Horizon {value}, Java {row[key]}"
                        if not args.diagnostics:
                            raise RuntimeError(detail)
                        first_difference = first_difference or detail
                if tick == drive:
                    control.call("key", "w", "down")
                    if branching:
                        control.call("key", steering_key, "down")
                    control.call("wait", 3)
                if tick == coast:
                    control.call("key", "w", "up")
                    if branching:
                        control.call("key", steering_key, "up")
                    control.call("wait", 3)
                # Client motion continues while the measured server clock is frozen.
                # Keep the held driver within range before each measured step.
                if drive + 8 <= tick < coast:
                    seat_x = X + (found[1] + found[4]) / 2
                    seat_z = Z + (found[3] + found[6]) / 2
                    control.command(f"/tp @s {seat_x:.6f} {Y + 4} {seat_z + 1.5:.6f}")
                    control.call("wait", 3)
                if args.visual and tick == 79:
                    seat_x = X + (found[1] + found[4]) / 2
                    seat_z = Z + (found[3] + found[6]) / 2
                    control.commands((
                        "/time set noon",
                        f"/tp @s {seat_x + 5.5:.6f} {Y + 6} {seat_z - 4:.6f}",
                    ))
                    control.call("wait", 3)
                    control.call("look-at", seat_x, Y + 1.1, seat_z)
                    control.call("key", "f1", "tap")
                    control.call("wait", 4)
                    control.call("screenshot", ROOT / ".local/curved-train.png")
                    control.call("key", "f1", "tap")
                    control.command(f"/tp @s {seat_x:.6f} {Y + 4} {seat_z + 1.5:.6f}")
                    control.call("wait", 3)
            if first_difference:
                raise RuntimeError(first_difference)
    print(f"Curved train speed and four wheel positions matched Java for all {len(expected)} ticks.")
    if has_signals:
        print(f"All {len(lamp_keys)} signal lamp states matched on all {len(expected)} ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    scenario = parser.add_mutually_exclusive_group()
    scenario.add_argument("--signals", action="store_true")
    scenario.add_argument("--steer-right", action="store_true")
    scenario.add_argument("--steer-left", action="store_true")
    scenario.add_argument("--branch-signals", action="store_true")
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--tolerance", type=float, default=7.0e-6)
    run(parser.parse_args())
