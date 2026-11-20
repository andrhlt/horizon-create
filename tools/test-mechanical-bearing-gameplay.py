#!/usr/bin/env python3
"""Check bounded Mechanical Bearing placement, controls, modes and idle persistence."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world

BEARING = "create:mechanical_bearing"
MOTOR = "create:creative_motor"


def coords(pos):
    return " ".join(map(str, pos))


def field(data, name):
    match = re.search(rf"\b{re.escape(name)}: (-?\d+(?:\.\d+)?)(?:[fd])?", data)
    return float(match[1]) if match else 0.0


def block_data(control, pos):
    return control.command(f"/data get block {coords(pos)}")


def advance(control, ticks):
    for _ in range(ticks):
        control.step_to(control.clock() + 1)


def survival_placement(args):
    # The client ray hits the support's east face from this standing position,
    # so vanilla placement puts the bearing in the adjacent east cell.
    target, support = (9, 99, -10), (8, 99, -10)
    with fixture_world(args, "MechanicalBearingPlacement", render=True, pack=args.pack) as control:
        control.commands((
            "/gamemode survival",
            f"/setblock {coords(support)} minecraft:smooth_stone",
            f"/item replace entity @s hotbar.0 with {BEARING} 1",
            "/tp @s 11.5 100 -9.5",
        ))
        control.call("wait", 3)
        control.call("select", BEARING)
        control.call("look-at", support[0] + 0.5, support[1] + 0.999, support[2] + 0.5)
        control.call("wait", 2)
        control.call("mouse", "right", "down")
        control.call("wait", 1)
        control.call("mouse", "right", "up")
        control.call("wait", 3)
        state = control.call("block", *target)["state"]
        remaining = control.call("inventory")["counts"].get(BEARING, 0)
        if not state.startswith(BEARING + "[") or remaining != 0:
            raise RuntimeError(f"Survival placement failed: state={state}, held count={remaining}.")
    print("Mechanical Bearing survival placement consumed one item and placed the block.")


def powered_rig(control, bearing, mode):
    x, y, z = bearing
    anchor = (x, y + 1, z)
    motor = (x, y - 1, z)
    control.commands((
        f"/setblock {coords(bearing)} {BEARING}[facing=up]",
        f"/data merge block {coords(bearing)} {{ScrollValue:{mode}}}",
        f"/setblock {coords(anchor)} minecraft:smooth_stone",
        f"/setblock {coords(motor)} {MOTOR}[facing=up]{{ScrollValue:0}}",
    ))
    return anchor, motor


def toggle(control, bearing):
    x, y, z = bearing
    control.command(f"/tp @s {x + 0.5} {y + 1} {z + 3.5}")
    control.command("/item replace entity @s weapon.mainhand with minecraft:air")
    control.call("interact", x, y, z, "south")
    # The use handler schedules assembly for the following server tick.
    control.step_to(control.clock() + 1)
    control.step_to(control.clock() + 1)


def mode_case(control, bearing, mode, ticks, should_restore):
    anchor, motor = powered_rig(control, bearing, mode)
    control.command(f"/data merge block {coords(motor)} {{ScrollValue:16}}")
    toggle(control, bearing)
    before = block_data(control, bearing)
    if "MovedBlocks" not in before or field(before, "Running") != 1:
        raise RuntimeError(f"Mode {mode} did not assemble a valid payload: {before}")
    advance(control, ticks)
    moving = block_data(control, bearing)
    angle = field(moving, "Angle")
    if "MovedBlocks" not in moving or angle == 0:
        raise RuntimeError(f"Mode {mode} failed to move its payload: {moving}")
    control.command(f"/data merge block {coords(motor)} {{ScrollValue:0}}")
    control.step_to(control.clock() + 1)
    stopped = block_data(control, bearing)
    assembled = "MovedBlocks" in stopped
    if assembled == should_restore:
        raise RuntimeError(
            f"Mode {mode} at {angle:g} degrees had wrong stop behavior; "
            f"expected restored={should_restore}, state={stopped}"
        )
    if not assembled and control.call("block", *anchor)["block"] != "minecraft:smooth_stone":
        raise RuntimeError(f"Mode {mode} failed to restore the payload at {anchor}.")


def obstructed(control, bearing):
    x, y, z = bearing
    anchor, motor = (x, y + 1, z), (x, y - 1, z)
    control.commands((
        f"/setblock {coords(bearing)} {BEARING}[facing=up]",
        f"/setblock {coords(anchor)} minecraft:bedrock",
        f"/setblock {coords(motor)} {MOTOR}[facing=up]{{ScrollValue:0}}",
        f"/data merge block {coords(motor)} {{ScrollValue:16}}",
    ))
    toggle(control, bearing)
    result = block_data(control, bearing)
    anchor_state = control.call("block", *anchor)["block"]
    if field(result, "Running") != 0 or anchor_state != "minecraft:bedrock":
        raise RuntimeError(f"Obstructed bearing assembled or changed its anchor: {result}; {anchor_state}")


def controls_and_modes(args):
    with fixture_world(args, "MechanicalBearingControls", pack=args.pack) as control:
        control.command("/tp @s 8.5 104 13.5")
        bearing = (8, 104, 10)
        anchor, motor = powered_rig(control, bearing, 0)
        control.command(f"/data merge block {coords(motor)} {{ScrollValue:16}}")
        toggle(control, bearing)
        assembled = block_data(control, bearing)
        if "MovedBlocks" not in assembled or field(assembled, "Running") != 1:
            raise RuntimeError(f"Empty-hand start failed: {assembled}")
        advance(control, 4)
        first_angle = field(block_data(control, bearing), "Angle")
        control.command(f"/data merge block {coords(motor)} {{ScrollValue:-16}}")
        control.step_to(control.clock() + 1)
        reversed_angle = field(block_data(control, bearing), "Angle")
        if not first_angle or reversed_angle == first_angle:
            raise RuntimeError(f"Powered reversal did not change bearing angle: {first_angle} -> {reversed_angle}")
        control.command(f"/data merge block {coords(motor)} {{ScrollValue:0}}")
        advance(control, 1)
        toggle(control, bearing)
        if "MovedBlocks" in block_data(control, bearing):
            raise RuntimeError("Empty-hand stop failed to disassemble a valid bearing.")

        # ScrollValue 0 places the payload at any angle on stop. Mode 1 only
        # places it close to the initial angle; mode 2 never auto-places it.
        mode_case(control, (15, 104, 10), 0, 5, True)
        mode_case(control, (22, 104, 10), 1, 1, True)
        mode_case(control, (29, 104, 10), 1, 8, False)
        mode_case(control, (36, 104, 10), 2, 1, False)
        obstructed(control, (43, 104, 10))

        idle = (50, 104, 10)
        powered_rig(control, idle, 2)
        control.call("save")
        control.restart()
        persisted = block_data(control, idle)
        if field(persisted, "Running") != 0 or field(persisted, "ScrollValue") != 2:
            raise RuntimeError(f"Idle bearing setting did not survive save/reopen: {persisted}")
    print("Mechanical Bearing controls, obstruction, mode stop behavior and idle setting reopen passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    survival_placement(args)
    controls_and_modes(args)


if __name__ == "__main__":
    main()
