#!/usr/bin/env python3
"""Verify Java's break order when a powered gearbox closes a controller loop."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world


def coords(pos):
    return " ".join(map(str, pos))


def speed(control, pos):
    data = control.command(f"/data get block {coords(pos)}")
    match = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)", data)
    if match is None:
        raise RuntimeError(f"No kinetic speed at {pos}: {data}")
    return float(match[1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    args = parser.parse_args()

    controller = (10, 101, -10)
    cog = (10, 102, -10)
    loop_gear = (9, 101, -10)
    original_network = (
        controller, cog, loop_gear, (9, 101, -11), (9, 102, -11),
        (10, 102, -11), (11, 101, -10),
    )
    inserted_gear = loop_gear

    with fixture_world(args, "RotationSpeedControllerPoweredLoopClose") as control:
        control.commands((
            "/fill 5 100 -13 20 104 -7 minecraft:air",
            "/tp @s 6 101 -10",
            f"/setblock {coords(controller)} create:rotation_speed_controller[axis=x]",
            f"/data merge block {coords(controller)} {{ScrollValue:24}}",
            f"/setblock {coords(cog)} create:large_cogwheel[axis=z]",
            f"/setblock {coords((9, 101, -11))} create:gearbox[axis=x]",
            f"/setblock {coords((9, 102, -11))} create:gearbox[axis=z]",
            f"/setblock {coords((10, 102, -11))} create:gearbox[axis=y]",
        ))
        start = control.clock()
        for tick in range(1, 8):
            control.step_to(start + tick)
            if tick == 2:
                motor = (11, 101, -10)
                control.commands((
                    f"/setblock {coords(motor)} create:creative_motor[facing=west]",
                    f"/data merge block {coords(motor)} {{ScrollValue:-24}}",
                ))

        control.command(f"/setblock {coords(inserted_gear)} create:gearbox[axis=y]")
        control.step_to(start + 8)
        state_at_break_tick = control.call("block", *inserted_gear)
        if state_at_break_tick.get("block") != "minecraft:air":
            entity_at_break_tick = control.command(
                f"/data get block {coords(inserted_gear)}"
            )
            if "not a block entity" not in entity_at_break_tick.lower():
                raise RuntimeError(
                    "Expected Java's tick-8 loop break to remove the gearbox entity; "
                    f"got block={state_at_break_tick}, entity={entity_at_break_tick}"
                )
        control.step_to(start + 9)

        state = control.call("block", *inserted_gear)
        if state.get("block") != "minecraft:air":
            raise RuntimeError(
                f"Expected the gearbox removed on tick 8 to be air by tick 9; got {state}"
            )
        for pos in original_network:
            if pos == inserted_gear:
                continue
            actual = speed(control, pos)
            if actual != 24.0:
                raise RuntimeError(
                    f"Expected original network at {pos} to retain +24 RPM after "
                    f"the loop break, got {actual}"
                )

    print("Powered loop closure removed the gearbox by tick 8, cleared its block state by tick 9, and retained +24 RPM.")


if __name__ == "__main__":
    main()
