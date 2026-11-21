#!/usr/bin/env python3
"""Check Desk Bell support loss and idle/active save and reopen."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world

BELL = "create:desk_bell"
BELL_POS = (9, 171, 20)
SUPPORT = (9, 171, 21)
WIRE = (10, 171, 20)


def bell_state(control):
    block = control.call("block", *BELL_POS)
    if block["block"] != BELL:
        raise RuntimeError(f"Desk Bell missing at {BELL_POS}: {block}")
    return dict(re.findall(r"(\w+)=(\w+)", block["state"]))


def wire_power(control):
    block = control.call("block", *WIRE)
    match = re.search(r"power=(\d+)", block["state"])
    if match is None:
        raise RuntimeError(f"Could not read adjacent Desk Bell redstone output: {block}")
    return int(match.group(1))


def prepare(control):
    control.commands((
        "/fill 8 170 19 10 170 21 minecraft:stone",
        f"/setblock {SUPPORT[0]} {SUPPORT[1]} {SUPPORT[2]} minecraft:stone",
        f"/setblock {BELL_POS[0]} {BELL_POS[1]} {BELL_POS[2]} {BELL}[facing=north]",
        f"/setblock {WIRE[0]} {WIRE[1]} {WIRE[2]} minecraft:redstone_wire",
        "/tp @s 9.5 171 22.5",
    ))
    control.call("look-at", 9.5, 171.35, 20.5)
    control.call("wait", 2)


def ring(control):
    control.command("/tp @s 9.5 171 22.5")
    control.call("look-at", 9.5, 171.35, 20.5)
    control.call("wait", 2)
    hit = control.call("looking-at").get("block") or {}
    if hit.get("pos") != list(BELL_POS):
        raise RuntimeError(f"Player was not targeting the Desk Bell before ringing: {hit}")
    control.call("mouse", "right", "click")
    control.call("wait", 2)
    if bell_state(control).get("powered") != "true":
        raise RuntimeError("Player ring did not power the Desk Bell.")


def run_support(args):
    with fixture_world(args, "Desk-bell-support", render=True, pack=args.pack) as world:
        prepare(world)
        world.command(f"/setblock {SUPPORT[0]} {SUPPORT[1]} {SUPPORT[2]} minecraft:air")
        state = bell_state(world)
        if state.get("facing") != "north" or state.get("powered") != "false":
            raise RuntimeError(f"Removing adjacent support changed Desk Bell unexpectedly: {state}")
        ring(world)
    print("Removing the Desk Bell's adjacent block preserved its state and the bell remained usable.")


def run_persistence(args):
    with fixture_world(args, "Desk-bell-reopen", render=True, pack=args.pack) as world:
        prepare(world)
        world.command(f"/setblock {BELL_POS[0]} {BELL_POS[1]} {BELL_POS[2]} {BELL}[facing=west,waterlogged=true]")
        idle = bell_state(world)
        if wire_power(world) != 0:
            raise RuntimeError("Idle Desk Bell redstone output was not zero before saving.")
        world.command("/save-all flush")
        world.restart()
        idle_after = bell_state(world)
        expected_idle = {"facing": "west", "powered": "false", "waterlogged": "true"}
        if any(idle.get(k) != v for k, v in expected_idle.items()) or any(
            idle_after.get(k) != v for k, v in expected_idle.items()
        ):
            raise RuntimeError(f"Idle state changed across save/reopen: {idle} -> {idle_after}")
        if wire_power(world) != 0:
            raise RuntimeError("Idle Desk Bell redstone output changed across save/reopen.")

        world.command(f"/setblock {SUPPORT[0]} {SUPPORT[1]} {SUPPORT[2]} minecraft:air")
        world.command(f"/setblock {BELL_POS[0]} {BELL_POS[1]} {BELL_POS[2]} {BELL}[facing=north,waterlogged=false]")
        world.call("look-at", 9.5, 171.35, 20.5)
        world.call("wait", 2)
        ring(world)
        if wire_power(world) != 15:
            raise RuntimeError("Active Desk Bell did not power its adjacent redstone wire.")
        world.command("/save-all flush")
        world.restart()
        active = bell_state(world)
        if active.get("facing") != "north" or active.get("powered") != "true":
            raise RuntimeError(f"Active powered state changed across save/reopen: {active}")
        if wire_power(world) != 15:
            raise RuntimeError("Active Desk Bell redstone output changed across save/reopen.")
        world.call("look-at", 9.5, 171.35, 20.5)
        world.call("wait", 2)
        ring(world)
        for _ in range(21):
            world.step_to(world.clock() + 1)
        ended = bell_state(world)
        if ended.get("powered") != "false":
            raise RuntimeError(f"A post-reopen ring did not complete its 20-tick pulse: {ended}")
        if wire_power(world) != 0:
            raise RuntimeError("Desk Bell redstone output stayed powered after its post-reopen pulse.")
    print("Idle facing/waterlogging and active state/output survived save/reopen; a new ring reset after 20 ticks.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--support-removal", action="store_true")
    mode.add_argument("--persistence", action="store_true")
    args = parser.parse_args()
    (run_support if args.support_removal else run_persistence)(args)


if __name__ == "__main__":
    main()
