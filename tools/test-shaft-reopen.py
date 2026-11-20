#!/usr/bin/env python3
"""Check shaft casing, axis, inventory and kinetic operation after world reopen."""

import argparse
import importlib.util
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world


def load(name):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


casing = load("test-shaft-casing")


def speed(control, pos):
    response = control.command(f"/data get block {casing.coords(pos)} Speed")
    match = re.search(r"(-?\d+\.\d+)f\b", response)
    if match is None:
        raise RuntimeError(f"Could not read shaft speed at {pos}: {response}")
    return f"{float(match[1]):.4f}"


def snapshot(control, lane):
    pos, _, _, _, end, _, material = casing.LANES[lane]
    state = control.call("block", *pos)["state"]
    inventory = control.call("inventory")["counts"].get(f"create:{material}_casing", 0)
    return state, inventory, speed(control, end)


def advance(control, ticks):
    for _ in range(ticks):
        control.step_to(control.clock() + 1)


def interact(control, pos, item, *, wrench=False):
    x, y, z = pos
    control.command(f"/tp @s {x + 0.5:.2f} {y} {z - 2.1:.2f}")
    control.call("wait", 3)
    control.call("select", item)
    if wrench:
        control.call("key", "shift", "down")
        control.call("wait", 3)
    control.call("look-at", x + 0.5, y + 0.775, z + 0.5)
    control.call("wait", 2)
    control.call("mouse", "right", "down")
    control.call("wait", 1)
    control.call("mouse", "right", "up")
    if wrench:
        control.call("key", "shift", "up")
    control.call("wait", 4)


def run(args):
    with fixture_world(args, "ShaftReopen", render=True, pack=args.pack) as control:
        casing.setup(control)
        casing.apply(control, 0)
        casing.apply(control, 1)
        idle = (12, 101, -11)
        control.command(f"/setblock {casing.coords(idle)} create:shaft[axis=y]")
        control.command("/item replace entity @s hotbar.3 with create:andesite_casing 2")
        interact(control, idle, "create:andesite_casing")
        idle_cased = control.call("block", *idle)["state"]
        if not idle_cased.startswith("create:andesite_encased_shaft[axis=y"):
            raise RuntimeError(f"Andesite casing failed to preserve the Y axis: {idle_cased}")
        control.step_to(control.clock() + 1)

        before_x = snapshot(control, 0)
        before_z = snapshot(control, 1)
        before_idle = control.call("block", *idle)["state"]
        if not before_x[0].startswith("create:andesite_encased_shaft[axis=x"):
            raise RuntimeError(f"Expected the powered X shaft to be Andesite encased: {before_x}")
        if not before_z[0].startswith("create:brass_encased_shaft[axis=z"):
            raise RuntimeError(f"Expected the powered Z shaft to be Brass encased: {before_z}")
        if before_x[2] != "24.0000" or before_z[2] != "40.0000":
            raise RuntimeError(f"Unexpected active shaft RPM before save: {before_x}, {before_z}")
        if not before_idle.startswith("create:andesite_encased_shaft[axis=y"):
            raise RuntimeError(f"Unexpected idle Y shaft state before save: {before_idle}")

        control.restart(client=args.client)
        after_x = snapshot(control, 0)
        after_z = snapshot(control, 1)
        after_idle = control.call("block", *idle)["state"]
        if (after_x, after_z, after_idle) != (before_x, before_z, before_idle):
            raise RuntimeError(
                "Shaft state, casing inventory, RPM or idle Y-axis state changed after reopen: "
                f"before={(before_x, before_z, before_idle)}, "
                f"after={(after_x, after_z, after_idle)}"
            )

        interact(control, idle, "create:wrench", wrench=True)
        uncased_idle = control.call("block", *idle)["state"]
        if not uncased_idle.startswith("create:shaft[axis=y"):
            raise RuntimeError(f"Wrench removal failed to restore the Y-axis shaft: {uncased_idle}")
        if control.call("inventory")["counts"].get("create:andesite_casing", 0) != 4:
            raise RuntimeError("Y-axis encasing or wrench removal consumed the casing stack.")

        control.step_to(control.clock() + 1)
        resumed_x = snapshot(control, 0)
        resumed_z = snapshot(control, 1)
        if resumed_x[2] != "24.0000" or resumed_z[2] != "40.0000":
            raise RuntimeError(f"Powered shafts failed to resume after reopen: {resumed_x}, {resumed_z}")

        x_center = casing.LANES[0][0]
        x_end = casing.LANES[0][4]
        x_nonconnecting = (x_end[0], x_end[1], x_end[2] + 1)
        control.command(
            f"/setblock {casing.coords(x_nonconnecting)} create:shaft[axis=z]"
        )
        perpendicular = control.call("block", *x_nonconnecting)["state"]
        if not perpendicular.startswith("create:shaft[axis=z") or speed(control, x_end) != "24.0000":
            raise RuntimeError("A perpendicular neighboring shaft changed the active X-axis network.")

        control.command(f"/setblock {casing.coords(x_center)} minecraft:air")
        advance(control, 3)
        if speed(control, x_end) != "0.0000":
            raise RuntimeError("Removing an encased shaft did not disconnect the downstream X shaft.")
        control.command(
            f"/setblock {casing.coords(x_center)} create:andesite_encased_shaft[axis=x]"
        )
        advance(control, 3)
        if speed(control, x_end) != "24.0000":
            raise RuntimeError("Restoring an encased shaft did not reconnect the downstream X shaft.")

    print(
        "Andesite X and Brass Z shafts retained casing, RPM and inventory after reopen; "
        "an idle Y shaft retained its axis and casing, and wrench removal restored the shaft. "
        "Both powered shafts resumed at 24/40 RPM; a perpendicular neighbor stayed disconnected, "
        "and removing/restoring an encased shaft disconnected/reconnected the X network."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
