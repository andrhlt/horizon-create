#!/usr/bin/env python3
"""Compare actual hand-crank interactions in Horizon to the pinned Java GameTest."""

import argparse
import csv
from math import isclose
from pathlib import Path
import re
import time

from fixture_world import ROOT, fixture_world

CRANK = (6, 101, -10)
REAR = "6 101 -11"
FRONT = "6 101 -9"
STRESSOMETER = "6 101 -12"
PRESSES = {4: False, 9: False, 16: True, 31: True}


def tag_value(tag, key):
    match = re.search(rf"\b{key}: (-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)f\b", tag)
    if match is None:
        raise RuntimeError(f"Missing {key} in {tag}")
    return float(match[1])


def trace(log, prefix, time_tick):
    start = f"CREATE_HAND_CRANK_{prefix} {time_tick},"
    return [line[len(start):].split(",") for line in log.read_text().splitlines()
            if line.startswith(start)]


def tick_sample(log, control, time_tick):
    records = trace(log, "TICK", time_tick)
    if len(records) != 1:
        raise RuntimeError(f"Expected one crank tick at game time {time_tick}, got {records}")
    in_use, backwards, rpm, capacity, angle, velocity = records[0]
    rear, front, stressometer = control.commands(
        f"/data get block {pos}" for pos in (REAR, FRONT, STRESSOMETER)
    )
    status = control.call("lan", "status")
    exhaustion = next(player["food"][2] for player in status["guests"]
                      if player["name"] == status["host"])
    return (
        int(in_use), backwards, float(rpm), tag_value(rear, "Speed"),
        tag_value(front, "Speed"), tag_value(stressometer, "Speed"),
        float(capacity), float(angle), float(velocity), float(exhaustion),
    )


def verify_frame(log, time_tick, angle, velocity):
    stop = time.monotonic() + 4
    last = None
    while time.monotonic() < stop:
        for frame in trace(log, "FRAME", time_tick):
            partial, base_angle, angle_at_partial = map(float, frame[:3])
            base_vertices, handle_vertices = map(int, frame[3:])
            last = frame
            if (base_vertices > 0 and handle_vertices > 0
                    and isclose(base_angle, angle, abs_tol=0.00004)
                    and isclose(angle_at_partial, angle + partial * velocity, abs_tol=0.00004)):
                return
        time.sleep(0.03)
    raise RuntimeError(f"At world tick {time_tick}, expected a rendered handle at {angle} + "
                       f"{velocity} degrees/tick, got {last}.")


def setup(control):
    control.commands((
        "/fill 1 100 -15 10 100 -5 minecraft:smooth_stone",
        "/fill 1 101 -15 10 104 -5 minecraft:air",
        "/setblock 6 101 -11 create:shaft[axis=z]",
        "/setblock 6 101 -9 create:shaft[axis=z]",
        "/setblock 6 101 -12 create:stressometer[facing=up,axis_along_first=false]",
        "/setblock 6 101 -10 create:hand_crank[facing=south]",
        "/tp @s 4.5 101 -9.5",
        "/gamemode survival",
    ))


def verify_placement(control):
    coords = " ".join(map(str, CRANK))
    control.commands((
        f"/setblock {coords} minecraft:air",
        f"/setblock {FRONT} minecraft:air",
        "/item replace entity @s hotbar.0 with create:hand_crank 2",
    ))
    control.step_to(control.clock() + 1)
    control.call("wait", 4)
    control.call("select", "create:hand_crank")
    control.call("interact", 6, 100, -10, "up")
    mounted = control.call("block", *CRANK)["state"]
    if mounted != "create:hand_crank[facing=south,waterlogged=false]":
        raise RuntimeError(f"Expected the placed crank to align with the rear shaft, got {mounted}.")
    control.command(f"/setblock {REAR} minecraft:air")
    control.step_to(control.clock() + 1)
    unsupported = control.call("block", *CRANK)["state"]
    if unsupported != "minecraft:air":
        raise RuntimeError(f"The crank remained without its supporting shaft: {unsupported}.")
    control.command(f"/setblock {coords} minecraft:water")
    control.call("interact", 6, 100, -10, "up")
    waterlogged = control.call("block", *CRANK)["state"]
    if waterlogged != "create:hand_crank[facing=up,waterlogged=true]":
        raise RuntimeError(f"Expected an upward-facing waterlogged crank, got {waterlogged}.")


def compare(args):
    with (ROOT / "fixtures/hand-crank-java.csv").open() as fixture:
        expected = list(csv.reader(fixture))
    header, *expected_rows = expected
    trace_env = {"CREATE_HAND_CRANK_TRACE": ",".join(map(str, CRANK))}
    actual_rows = []
    with fixture_world(args, "HandCrank", render=True, env=trace_env, pack=args.pack) as control:
        setup(control)
        # The host's player body belongs to the integrated server's local
        # connection. LAN status reports its authoritative FoodData.
        control.call("lan", "open", "0", "commands", "force")
        control.call("look-at", 6.5, 101.4, -9.5)
        log = control.socket.parent / "ctl.log"
        start = control.clock() + 1
        mismatches = []
        for row in expected_rows:
            tick = int(row[0])
            control.step_to(start + tick)
            actual = tick_sample(log, control, start + tick)
            actual_rows.append((tick, *actual))
            for key, want, got in zip(header[1:], row[1:], actual, strict=True):
                matched = want == got if isinstance(got, str) else isclose(
                    float(want), got, abs_tol=0.000015, rel_tol=0.0,
                )
                if not matched:
                    mismatches.append((tick, key, want, got))
            if tick in (5, 17, 42) and not mismatches:
                verify_frame(log, start + tick, float(row[-3]), float(row[-2]))
            if tick in PRESSES:
                sneak = PRESSES[tick]
                if sneak:
                    control.call("key", "shift", "down")
                    control.call("wait", 3)
                try:
                    control.call("interact", *CRANK)
                finally:
                    if sneak:
                        control.call("key", "shift", "up")
        if not mismatches:
            verify_placement(control)
    with args.output.open("w") as comparison:
        writer = csv.writer(comparison)
        writer.writerow(header)
        writer.writerows(actual_rows)
    if mismatches:
        raise RuntimeError(f"{len(mismatches)} hand crank mismatches. First 12: {mismatches[:12]}")
    print(f"Hand crank matched Java for {len(actual_rows)} ticks and three rendered frames.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/hand-crank-horizon.csv")
    compare(parser.parse_args())


if __name__ == "__main__":
    main()
