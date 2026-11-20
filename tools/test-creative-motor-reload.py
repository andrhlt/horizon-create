#!/usr/bin/env python3
"""Save and reopen Creative Motors and compare their regenerated speed.

Java serializes `ScrollValue` and rebuilds the kinetic network on load. The
pinned trace records that a horizontal motor set to -24 drives its shaft at -24
on every later tick. This replay sets a horizontal and a vertical motor, saves
and reopens the world, and requires the setting, the motor speed and the driven
shaft speed to survive.
"""

import argparse
import importlib.util
from pathlib import Path

from fixture_world import fixture_world


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


motor = load("test-creative-motor")
controller = motor.controller
SETTING = -24
# A disconnected motor spins only itself: the idle case that must keep its
# setting and its own speed across a reopen.
IDLE = (11, 101, -13)
IDLE_SETTING = 40


def sample(control):
    settings = [controller.tag(control.command(f"/data get block {controller.coords(pos)}"), "ScrollValue", int)
                for pos in (motor.HORIZONTAL, motor.VERTICAL, IDLE)]
    speeds = [controller.tag(control.command(f"/data get block {controller.coords(pos)}"), "Speed", float)
              for pos in (*motor.POSITIONS, IDLE)]
    return settings, speeds


def verify(args):
    with fixture_world(args, "CreativeMotorReload", pack=args.pack) as control:
        motor.setup(control)
        for pos in (motor.HORIZONTAL, motor.VERTICAL):
            control.command(f"/data merge block {controller.coords(pos)} {{ScrollValue:{SETTING}}}")
        control.commands((
            f"/setblock {controller.coords(IDLE)} create:creative_motor[facing=south]",
            f"/data merge block {controller.coords(IDLE)} {{ScrollValue:{IDLE_SETTING}}}",
        ))
        for _ in range(3):
            control.step_to(control.clock() + 1)
        expected_settings = [SETTING, SETTING, IDLE_SETTING]
        expected_speeds = [*(float(SETTING) for _ in motor.POSITIONS), float(IDLE_SETTING)]
        settings, before = sample(control)
        if settings != expected_settings:
            raise RuntimeError(f"Pre-save settings did not settle: {settings}, expected {expected_settings}.")
        if before != expected_speeds:
            raise RuntimeError(f"Pre-save speeds did not settle to Java's settings: {before}, expected {expected_speeds}.")

        control.restart()
        control.call("wait", 4)
        for _ in range(2):
            control.step_to(control.clock() + 1)
        settings, after = sample(control)
        if settings != expected_settings:
            raise RuntimeError(f"Reopened Creative Motor lost a ScrollValue: {settings}, expected {expected_settings}.")
        if after != expected_speeds:
            raise RuntimeError(f"Reopened Creative Motor did not regenerate its settings: {after}, expected {expected_speeds}.")
    print(f"Two driven motors and one idle motor kept ScrollValue {SETTING}/{IDLE_SETTING} and their speeds after a world reopen.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
