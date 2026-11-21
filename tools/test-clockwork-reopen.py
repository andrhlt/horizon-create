#!/usr/bin/env python3
"""Save and reopen a powered Clockwork Bearing with two moving hands."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
import struct

from fixture_world import ROOT, fixture_world

clockwork = import_module("test-clockwork-bearing")
windmill = import_module("test-windmill")
ANGLES = ("hour_angle", "minute_angle")


def f32(value):
    return struct.unpack(">f", struct.pack(">f", float(value)))[0]


def snapshot(control):
    data = clockwork.observe(control, "east", control.clock())
    data["hands"] = len(data["hands"].split("|")) if data["hands"] else 0
    return data


def compare(reference, actual, *, angles=True):
    for key, expected in reference.items():
        if not angles and key in ANGLES:
            continue
        observed = actual[key]
        equal = (f32(expected) == f32(observed) if key in clockwork.NUMBER_KEYS
                 else str(observed) == expected)
        if not equal:
            raise RuntimeError(f"Clockwork reload {key}: Java {expected}, Horizon {observed}.")


def count_displays(control, *, tagged=False):
    tag = ",tag=clockwork_reopen_fixture" if tagged else ""
    result = control.command(f"/execute if entity @e[type=minecraft:block_display{tag}]")
    match = re.search(r"Count: (\d+)", result)
    return int(match[1]) if match else 0


def run(args):
    with (ROOT / "fixtures/clockwork-reopen-java.csv").open() as source:
        java = {row.pop("phase"): row for row in csv.DictReader(source)}
    with fixture_world(args, "Clockwork-reopen", render=True, pack=args.pack) as control:
        clockwork.setup(control)
        pos, motor, _ = clockwork.parts("east")
        at = windmill.coords(pos)
        control.command(f"/data merge block {at} {{ScrollValue:1}}")
        control.command("/save-all flush")
        control.restart()
        idle_mode = control.command(f"/data get block {at} ScrollValue")
        if not idle_mode.endswith("1"):
            raise RuntimeError(f"Idle Clockwork mode did not survive reopening: {idle_mode}.")
        running = control.command(f"/execute if data block {at} {{Running:1b}}")
        if running.startswith("Test passed") or count_displays(control):
            raise RuntimeError("Idle Clockwork reopening started the Bearing or created hand displays.")
        control.command(f"/data merge block {at} {{ScrollValue:0}}")
        control.command(f"/setblock {windmill.coords(motor)} create:creative_motor[facing=east]")
        start = control.clock()
        for tick in (1, 2):
            control.step_to(start + tick)
        x, y, z = pos
        control.command(f"/tp @s {x + 0.5} {float(y)} {z - 2.5}")
        control.call("wait", 4)
        before = snapshot(control)
        compare(java["before"], before)
        if count_displays(control) != 4:
            raise RuntimeError("The powered Clockwork Bearing should display four blocks.")
        control.command("/tag @e[type=minecraft:block_display] add clockwork_reopen_fixture")
        if count_displays(control, tagged=True) != 4:
            raise RuntimeError("The fixture could not mark all four original blocks.")

        control.restart()
        control.call("wait", 5)
        after = snapshot(control)
        compare(java["reopened"], after, angles=False)
        if count_displays(control) != 4 or count_displays(control, tagged=True) != 4:
            raise RuntimeError("Reloading replaced or duplicated part of a Clockwork hand.")
        expected = tuple(f32(before[key]) for key in ANGLES)
        observed = tuple(f32(after[key]) for key in ANGLES)
        step = tuple(f32(float(java["reopened"][key]) - float(java["before"][key])) for key in ANGLES)
        for _ in range(after["tick"] - before["tick"] + 1):
            if expected == observed:
                break
            expected = tuple(f32(a + b) for a, b in zip(expected, step, strict=True))
        else:
            raise RuntimeError(f"Clockwork angles did not resume from their saved values: {before}, {after}.")
        control.step_to(after["tick"] + 1)
        next_ = snapshot(control)
        if tuple(f32(next_[key]) for key in ANGLES) != tuple(
            f32(a + b) for a, b in zip(observed, step, strict=True)
        ):
            raise RuntimeError(f"The first controlled tick after reload differs from Java: {next_}.")
        control.call("look-at", x + 0.5, y + 0.91, z + 0.02)
        control.call("wait", 3)
        control.call("mouse", "right", "click")
        control.call("wait", 3)
        compare(java["stopped"], snapshot(control))
        if count_displays(control):
            raise RuntimeError("Stopping left part of a Clockwork hand behind.")
    print("Clockwork reopened with all original hand displays, matched the first Java step, and stopped cleanly.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
