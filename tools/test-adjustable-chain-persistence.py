#!/usr/bin/env python3
"""Save and reopen an idle configured chain, then an actively driven chain."""

import argparse
import importlib
from pathlib import Path

from fixture_world import fixture_world

chain = importlib.import_module("test-adjustable-chain-gearshift")
MOTORS = ((6, 100, -10), (12, 100, -10))
GEARSHIFTS = (chain.FORWARD, chain.REVERSE)
OUTPUTS = (chain.FORWARD_OUTPUT, chain.REVERSE_OUTPUT)


def nbt(control, pos):
    return chain.block_data(control, pos)


def rpm(control, pos):
    return chain.value(nbt(control, pos), "Speed", float)


def assert_connections(control):
    for pos, part in zip(GEARSHIFTS, ("start", "start"), strict=True):
        state = control.call("block", *pos)["state"]
        if not all(value in state for value in ("axis=y", "part=" + part, "axis_along_first=true")):
            raise RuntimeError(f"Chain connection changed across save/reopen at {pos}: {state}")
    for pos in ((7, 101, -10), (12, 101, -10)):
        state = control.call("block", *pos)["state"]
        if "part=end" not in state:
            raise RuntimeError(f"Encased chain connection changed across save/reopen at {pos}: {state}")


def assert_signal(control, wanted=3):
    for pos in GEARSHIFTS:
        got = chain.value(nbt(control, pos), "Signal", int)
        if got != wanted:
            raise RuntimeError(f"Saved chain signal at {pos} is {got}; expected {wanted}.")


def assert_active(control, expected):
    assert_signal(control)
    assert_connections(control)
    values = tuple(rpm(control, pos) for pos in (*GEARSHIFTS, *OUTPUTS))
    if values != expected:
        raise RuntimeError(f"Active chain changed speed/sign across save/reopen: {expected} -> {values}")


def advance(control, ticks):
    for _ in range(ticks):
        control.step_to(control.clock() + 1)


def verify(args):
    with fixture_world(args, "AdjustableChainPersistence", render=True, pack=args.pack) as control:
        chain.setup(control)
        chain.press(control, 3)
        advance(control, 2)
        assert_signal(control)
        assert_connections(control)

        control.commands(f"/setblock {chain.coords(pos)} minecraft:air" for pos in MOTORS)
        advance(control, 3)
        idle = tuple(rpm(control, pos) for pos in (*GEARSHIFTS, *OUTPUTS))
        if idle != (0.0, 0.0, 0.0, 0.0):
            raise RuntimeError(f"Expected a stationary configured chain before idle save, got {idle}")
        control.call("save")
        control.restart()
        assert_signal(control)
        assert_connections(control)
        idle_after_reload = tuple(rpm(control, pos) for pos in (*GEARSHIFTS, *OUTPUTS))
        if idle_after_reload != idle:
            raise RuntimeError(f"Idle chain changed across save/reopen: {idle} -> {idle_after_reload}")

        control.commands(
            f"/setblock {chain.coords(pos)} create:creative_motor[facing=up]" for pos in MOTORS
        )
        control.commands(
            f"/data merge block {chain.coords(pos)} {{ScrollValue:24}}" for pos in MOTORS
        )
        advance(control, 5)
        active = tuple(rpm(control, pos) for pos in (*GEARSHIFTS, *OUTPUTS))
        if active[0] == 0.0 or active[2] == 0.0 or active[3] == 0.0:
            raise RuntimeError(f"Expected active transmission in both connected setups, got {active}")
        control.call("save")
        control.restart()
        assert_signal(control)
        assert_connections(control)
        for _ in range(3):
            advance(control, 1)
            assert_active(control, active)
    print("Idle and active chain setups retained signal, connections, speed/sign, and resumed output after save/reopen.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
