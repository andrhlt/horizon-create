#!/usr/bin/env python3
"""Verify an idle connected conveyor pair survives save/reopen and restarts."""

import argparse
import importlib
import re
from pathlib import Path

from fixture_world import fixture_world


kinetics = importlib.import_module("test-chain-conveyor-kinetics")
A = (8, 102, -10)
EDGE = (7, 0, 0)
B = tuple(a + b for a, b in zip(A, EDGE))
MOTOR = (8, 101, -10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve())
    parser.add_argument(
        "--pack", type=Path,
        default=Path(__file__).resolve().parents[1] / ".local/create.hmod",
    )
    args = parser.parse_args()

    with fixture_world(args, "ChainConveyor-IdleReopen", pack=args.pack) as world:
        world.commands((
            "/fill 6 100 -12 17 105 -5 minecraft:air",
            f"/setblock {kinetics.coords(A)} create:chain_conveyor",
            f"/setblock {kinetics.coords(B)} create:chain_conveyor",
        ))
        kinetics.set_link(world, A, EDGE)
        kinetics.set_link(world, B, tuple(-axis for axis in EDGE))
        saved_clock = world.clock()
        world.call("save")
        world.env["HORIZON_STILL"] = "1"
        world.restart()
        assert world.clock() == saved_clock

        for pos, edge in ((A, EDGE), (B, tuple(-axis for axis in EDGE))):
            state = world.call("block", *pos)
            assert state["block"] == "create:chain_conveyor", state
            data = world.command(f"/data get block {kinetics.coords(pos)}")
            speed = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)f\b", data)
            assert speed is None or float(speed[1]) == 0.0, data
            vector = r"\s*,\s*".join(map(str, edge))
            assert re.search(rf"Connections:\s*\[\[I;\s*{vector}\s*\]\]", data), data
        world.commands((
            f"/setblock {kinetics.coords(MOTOR)} create:creative_motor[facing=up]",
            f"/data merge block {kinetics.coords(MOTOR)} {{ScrollValue:128}}",
        ))
        world.step_to(saved_clock + 1)
        actual = kinetics.speeds(world, (A, B))
        assert actual == (128.0, 128.0), actual
        print("Idle save/reopen retained both links and restarted at 128 RPM.")


if __name__ == "__main__":
    main()
