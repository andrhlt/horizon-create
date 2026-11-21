#!/usr/bin/env python3
"""Save and reopen an idle girder and an actively transmitting encased shaft."""

import argparse
import importlib.util
from pathlib import Path

from fixture_world import fixture_world

shaft_path = Path(__file__).with_name("test-metal-girder-shaft.py")
shaft_spec = importlib.util.spec_from_file_location("metal_girder_shaft", shaft_path)
shaft = importlib.util.module_from_spec(shaft_spec)
shaft_spec.loader.exec_module(shaft)


def state(control):
    return control.call("block", *shaft.BASE)["state"]


def rpm(control, pos):
    result = control.command(f"/data get block {shaft.coords(pos)} Speed")
    import re
    match = re.search(r"(-?\d+\.\d+)f\b", result)
    return float(match.group(1)) if match else 0.0


def verify(args):
    with fixture_world(args, "MetalGirderPersistence", render=True, pack=args.pack) as control:
        shaft.setup(control, 0)
        idle = state(control)
        control.call("save")
        control.restart()
        if state(control) != idle:
            raise RuntimeError(f"Idle girder changed across reopen: {idle} -> {state(control)}")

        shaft.interact(control, 0, True)
        control.step_to(control.clock() + 1)
        output = shaft.neighbors(0)[1]
        active = (state(control), rpm(control, output))
        if not active[0].startswith(shaft.ENCASED) or active[1] != 32.0:
            raise RuntimeError(f"Expected a waterlogged encased shaft transmitting 32 RPM, got {active}")
        control.call("save")
        control.restart()
        if state(control) != active[0]:
            raise RuntimeError(f"Encased shaft state changed across reopen: {active[0]} -> {state(control)}")
        resumed = rpm(control, output)
        if resumed != active[1]:
            raise RuntimeError(f"Shaft output changed across reopen: {active[1]} -> {resumed}")
    print("Idle girder state and active waterlogged shaft transmission survived save/reopen.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    verify(parser.parse_args())
