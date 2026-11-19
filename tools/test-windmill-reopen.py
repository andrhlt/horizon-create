#!/usr/bin/env python3
"""Compare Windmill save/reload observations and check stable blade ownership."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
import re
import struct

from fixture_world import ROOT, fixture_world

windmill = import_module("test-windmill")


def count(control, tagged=False):
    extra = ",tag=windmill_reopen_fixture" if tagged else ""
    response = control.command(f"/execute if entity @e[type=minecraft:block_display{extra}]")
    match = re.search(r"Count: (\d+)", response)
    if match:
        return int(match[1])
    if response.startswith("Test failed"):
        return 0
    raise RuntimeError(f"Unexpected display count response: {response}")


def f32(value):
    return struct.unpack(">f", struct.pack(">f", float(value)))[0]


def sample(control, rig):
    return windmill.observe(control, windmill.WINDMILLS[rig], windmill.SAILS[rig], control.clock(), rig)


def run(args):
    with (ROOT / "fixtures/windmill-reopen-java.csv").open() as source:
        java = {row.pop("phase"): row for row in csv.DictReader(source)}
    initial = argparse.Namespace(**vars(args))
    initial.client = args.initial_client or args.client
    with fixture_world(initial, "Windmill-reopen", render=True, pack=args.pack) as control:
        windmill.setup(control)
        x, y, z = windmill.WINDMILLS[1]
        control.command(f"/setblock {x - 2} {y} {z} minecraft:air")
        windmill.short_press(control, windmill.WINDMILLS[1])
        control.step_to(control.clock() + 1)
        windmill.operate(control)
        control.step_to(control.clock() + 1)
        control.command("/tp @s 5.5 181.0 33.5")
        control.call("wait", 3)
        before = sample(control, 1)
        windmill.compare(java["before"], before)
        before_large = sample(control, 2)
        if count(control) != 24:
            raise RuntimeError("Expected 24 original blade entities before saving.")
        control.command("/tag @e[type=minecraft:block_display] add windmill_reopen_fixture")
        if count(control, tagged=True) != 24:
            raise RuntimeError("The fixture could not mark every original blade.")

        control.restart(client=args.client)
        control.call("wait", 5)
        reopened = sample(control, 1)
        reopened_large = sample(control, 2)
        physical_state = {key: value for key, value in java["reopened"].items() if key != "angle"}
        windmill.compare(physical_state, reopened)
        if count(control) != 24 or count(control, tagged=True) != 24:
            raise RuntimeError("Reopening lost, replaced or duplicated original blade entities.")
        # The full Horizon client startup can run ticks before the control
        # socket accepts /tick freeze. Both rotors must resume from the saved
        # angle and advance together within that measured startup interval.
        small = f32(before["angle"])
        large = f32(before_large["angle"])
        delta = f32(float(java["reopened"]["angle"]) - float(java["before"]["angle"]))
        for _ in range(reopened["tick"] - before["tick"] + 1):
            if (small, large) == (f32(reopened["angle"]), f32(reopened_large["angle"])):
                break
            small, large = f32(small + delta), f32(large + 2 * delta)
        else:
            raise RuntimeError(f"Reloaded angles did not resume from the saved values: {before}, {reopened}, {reopened_large}.")
        control.step_to(reopened["tick"] + 1)
        advanced = sample(control, 1)
        if f32(advanced["angle"]) != f32(small + delta) or count(control) != 24:
            raise RuntimeError(f"The first controlled tick after reload differed from Java: {advanced}")

        # Stop the two active rigs without retrying the seven-sail failure.
        for rig in (1, 2):
            x, y, z = windmill.WINDMILLS[rig]
            control.command(f"/tp @s {x + 0.5} {float(y)} {z - 2.5}")
            control.call("wait", 3)
            control.call("look-at", x + 0.5, y + 0.91, z + 0.02)
            control.call("wait", 2)
            control.call("mouse", "right", "click")
            control.call("wait", 2)
            stopped = sample(control, rig)
            expected = dict(java["stopped"], present=str(windmill.SAILS[rig]))
            windmill.compare(expected, stopped)
        if count(control):
            raise RuntimeError("Stopping the reopened Windmills left blade entities behind.")
    print("Running Windmills retained all original blades after reload and matched Java's resumed angular step and restored blocks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--initial-client", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
