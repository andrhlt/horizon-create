#!/usr/bin/env python3
"""Replay Java's vertical standing collision for the original flat elevator deck.

Apply java-elevator-standing-collider-trace.patch in the pinned Java checkout.
Ride the original flat elevator in two local clients with
-Dparity.elevator.standing=true, then pass both client logs to this script.
Input fields describe player state after vanilla travel and Create's ray
correction. Rider fields describe the end of Create's collision callback.
The cabin's own prior position can reset on a force-sync packet, so the
fixture records it separately from the previous observation's cabin position.
"""

import argparse
import csv
from math import isclose
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/elevator-standing-java.csv"
COLUMNS = ("role", "tick", "cabin_y", "collision_previous_y", "input_y", "input_v",
           "rider_y", "rider_v", "hard_collision")

BOX_INFLATION = 1e-7
SEPARATION = 1e-4
MIN_MOVEMENT = 0.003
GRAVITY = 0.08
DRAG = struct.unpack("f", struct.pack("f", 0.98))[0]


def sign(value):
    return (value > 0) - (value < 0)


def solve(previous, cabin, collision_previous):
    """Advance an unmounted rider on an isolated, horizontally supported flat deck."""
    previous_cabin, feet, velocity = previous
    last_offset = feet - previous_cabin
    movement = velocity if abs(velocity) >= MIN_MOVEMENT else 0.0
    feet += movement
    velocity = (movement - GRAVITY) * DRAG
    cabin_motion = cabin - collision_previous
    deck = cabin + 1.0

    # Create can ray-correct a locally tracked rider before the geometric sweep.
    trend = sign(feet - cabin - last_offset)
    speed_squared = cabin_motion ** 2
    if (trend and trend != sign(cabin_motion - velocity) and speed_squared >= 0.05
            and (trend < 0 or speed_squared >= 0.1)):
        feet = deck

    gap = feet - deck
    hard = gap <= BOX_INFLATION
    # The vertical pass sweeps after applying discrete separation.
    distance = SEPARATION if hard else gap - BOX_INFLATION
    if 0.0 < distance < cabin_motion - velocity:
        next_velocity = cabin_motion - distance
    else:
        next_velocity = velocity
    if hard and next_velocity < 0.0:
        next_velocity = cabin_motion
    next_feet = deck + BOX_INFLATION + SEPARATION if hard else feet
    return feet, velocity, next_feet, next_velocity, hard


def capture(path):
    """Extract grounded rows from a client log recorded with the Java trace patch."""
    previous = None
    grounded = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if found := re.search(r"STANDING_MOTION ([^\x1b]+)", line):
            tick, role, cabin, collision_previous, _, _, input_y, input_v, _, _, _, rider_y, hard, support, on_ground = (
                found[1].split(",")
            )
            previous = (role, tick, cabin, collision_previous, input_y, input_v, rider_y, hard)
            grounded = support == on_ground == "true"
        if found := re.search(r"STANDING_VELOCITY (\d+),([^\x1b]+)", line):
            if previous is None or previous[1] != found[1]:
                raise ValueError(f"Unpaired velocity at world tick {found[1]} in {path}")
            if grounded:
                yield dict(zip(COLUMNS, (*previous[:-1], found[2], previous[-1]), strict=True))
            previous = None


def verify(rows):
    previous = {}
    grounded_samples = 0
    for row in rows:
        role = row["role"]
        cabin, collision_previous, input_y, input_v, rider_y, rider_v = (
            float(row[column]) for column in COLUMNS[2:-1]
        )
        if role not in previous:
            previous[role] = (cabin, rider_y, rider_v)
            continue
        observed = (input_y, input_v, rider_y, rider_v, row["hard_collision"] == "true")
        predicted = solve(previous[role], cabin, collision_previous)
        if not all(isclose(actual, expected, rel_tol=0.0, abs_tol=2e-12)
                   for actual, expected in zip(predicted, observed, strict=True)):
            raise ValueError(f"{role} world tick {row['tick']}: predicted {predicted}, observed {observed}")
        previous[role] = (cabin, predicted[2], predicted[3])
        grounded_samples += 1
    if len(previous) != 2 or grounded_samples == 0:
        raise ValueError("Expected two local Java client traces.")
    print(f"Matched all {grounded_samples} Java standing collision observations across both clients.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="*", type=Path, help="Two instrumented Java client logs")
    parser.add_argument("--output", type=Path, help="Write captured CSV after verifying it")
    args = parser.parse_args()
    if args.logs and len(args.logs) != 2:
        parser.error("pass both client logs")
    if args.logs:
        rows = [row for log in args.logs for row in capture(log)]
    else:
        with FIXTURE.open(newline="") as source:
            rows = list(csv.DictReader(source))
    verify(rows)
    if args.output:
        with args.output.open("w", newline="") as output:
            writer = csv.DictWriter(output, COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
