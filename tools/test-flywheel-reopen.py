#!/usr/bin/env python3
"""Check an idle and powered Flywheel assembly across a world save/reopen."""

import argparse
import importlib.util
from pathlib import Path

from fixture_world import fixture_world

spec = importlib.util.spec_from_file_location(
    "test_flywheel", Path(__file__).with_name("test-flywheel.py"))
flywheel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flywheel)
MOTOR, SHAFT, WHEEL, number = flywheel.MOTOR, flywheel.SHAFT, flywheel.WHEEL, flywheel.number

COG = "5 106 -10"


def sample(control):
    wheel, shaft, cog, motor = control.commands((
        f"/data get block {WHEEL}", f"/data get block {SHAFT}",
        f"/data get block {COG}", f"/data get block {MOTOR}",
    ))
    if "create:flywheel" not in wheel:
        raise RuntimeError(f"Flywheel block entity did not load after reopen: {wheel}")
    return (number(wheel, "Speed"), number(shaft, "Speed"),
            number(cog, "Speed"), number(motor, "ScrollValue"))


def run(args):
    with fixture_world(args, "FlywheelReopen", pack=args.pack) as control:
        control.commands((
            f"/setblock {MOTOR} create:creative_motor[facing=east]",
            f"/data merge block {MOTOR} {{ScrollValue:64}}",
            f"/setblock {WHEEL} create:flywheel[axis=x]",
            f"/setblock {SHAFT} create:shaft[axis=x]",
            f"/setblock {COG} create:cogwheel[axis=x]",
        ))
        for _ in range(3):
            control.step_to(control.clock() + 1)
        idle = sample(control)
        if idle != (64.0, 64.0, 0.0, 64.0):
            raise RuntimeError(f"Expected the idle Flywheel to pass axial rotation without meshing: {idle}")

        # Remove and restore the source to check powered/coasting operation and
        # reconnection before saving an active assembly.
        control.command(f"/setblock {MOTOR} minecraft:air")
        for _ in range(3):
            control.step_to(control.clock() + 1)
        stopped = sample(control)
        if stopped[:3] != (0.0, 0.0, 0.0):
            raise RuntimeError(f"Removing the motor left rotation in the assembly: {stopped}")
        control.command(f"/setblock {MOTOR} create:creative_motor[facing=east]")
        control.command(f"/data merge block {MOTOR} {{ScrollValue:-32}}")
        for _ in range(3):
            control.step_to(control.clock() + 1)
        active = sample(control)
        if active != (-32.0, -32.0, 0.0, -32.0):
            raise RuntimeError(f"Reconnected Flywheel assembly did not reverse: {active}")

        control.restart()
        control.call("wait", 4)
        for _ in range(3):
            control.step_to(control.clock() + 1)
        reopened = sample(control)
        if reopened != active:
            raise RuntimeError(f"Active assembly changed across save/reopen: before={active}, after={reopened}")
        print(f"Flywheel idle {idle}, stopped {stopped}, reconnected/reopened active {reopened}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
