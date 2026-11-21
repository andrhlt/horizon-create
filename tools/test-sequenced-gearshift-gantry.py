#!/usr/bin/env python3
"""Check sequencer distance limits on a downstream gantry gear ratio."""
import argparse
from math import isclose
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

BASE = (3, 96, -12)
SEQUENCER = (10, 101, -10)
GANTRY = "@e[type=minecraft:marker,tag=create_gantry_payload,limit=1]"
TEMPLATE = Path("gametest/contraptions/roller_filling.nbt")


def run(args):
    x, y, z = BASE
    sx, sy, sz = SEQUENCER
    with fixture_world(args, "Sequenced-gantry-distance", TEMPLATE) as control:
        control.command(f"/place template create:{TEMPLATE.with_suffix('')} {x} {y} {z}")
        control.commands((
            f"/setblock {sx} {sy} {sz} create:sequenced_gearshift[axis=x,state=0,vertical=true]",
            f'/data merge block {sx} {sy} {sz} {{Instructions:[{{Type:"TURN_DISTANCE",Value:1,Modifier:"FORWARD"}},{{Type:"END",Value:1,Modifier:"FORWARD"}}]}}',
            f"/setblock {sx} {sy} {sz-1} minecraft:redstone_block",
        ))

        offsets = []
        for _ in range(10):
            control.step_to(control.clock() + 1)
            report = control.command(f"/data get entity {GANTRY} CreateGantry.Offset")
            match = re.search(r"(-?\d+(?:\.\d+)?)d", report)
            if match:
                offsets.append(float(match[1]))

        # The fixture's gearbox makes the gantry shaft run at 32 RPM from the
        # sequencer's 128 RPM input. Java's distance context therefore limits
        # this 1-block instruction to (1 / 128) * 32 = 0.25 gantry blocks.
        if not offsets or not any(isclose(offset, 0.25, abs_tol=1e-6) for offset in offsets):
            raise RuntimeError(f"Expected the gantry to stop at the Java distance limit 0.25, got {offsets}.")
        if any(abs(offset) > 0.25 + 1e-6 for offset in offsets):
            raise RuntimeError(f"Gantry exceeded its sequenced distance limit: {offsets}.")
        if "No entity was found" not in report:
            raise RuntimeError(f"Gantry should disassemble after the sequence ends, got {report}.")
        carriage = control.call("block", 9, 101, -10)["block"]
        if not carriage.startswith("create:gantry_carriage"):
            raise RuntimeError(f"Gantry carriage was not restored after the sequence: {carriage}.")

    print("Sequenced gantry stopped at the Java 0.25-block distance limit and restored its carriage.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
