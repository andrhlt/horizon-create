#!/usr/bin/env python3
"""Check latch block states and redstone operation across world reopen."""

import argparse
from pathlib import Path

from fixture_world import fixture_world

TOGGLE = (8, 120, 8)
LATCH = (8, 124, 8)


def coords(pos):
    return " ".join(map(str, pos))


def state(world, pos):
    return world.call("block", *pos)["state"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()

    with fixture_world(args, "CreateLatchPersistence", render=False, pack=args.pack,
                       artifact_dir=Path(".local/app-2035-evidence")) as world:
        world.commands((
            "/fill 5 119 5 12 125 11 minecraft:smooth_stone",
            f"/setblock {coords(TOGGLE)} create:powered_toggle_latch[facing=east,powered=false,powering=true]",
            f"/setblock {coords(LATCH)} create:powered_latch[facing=east,powered=false,powered_side=false,powering=true]",
            f"/setblock {TOGGLE[0]-1} {TOGGLE[1]} {TOGGLE[2]} minecraft:redstone_wire[power=0]",
            f"/setblock {LATCH[0]-1} {LATCH[1]} {LATCH[2]} minecraft:redstone_wire[power=0]",
        ))
        idle = (state(world, TOGGLE), state(world, LATCH))
        world.command("/save-all flush")
        world.restart()
        reopened_idle = (state(world, TOGGLE), state(world, LATCH))
        if reopened_idle != idle:
            raise RuntimeError(f"Idle latch state/output changed across reopen: {idle} -> {reopened_idle}")

        # East is the rear input for both blocks; south is a side input for the Powered Latch.
        world.commands((
            f"/setblock {TOGGLE[0]+1} {TOGGLE[1]} {TOGGLE[2]} minecraft:redstone_block",
            f"/setblock {LATCH[0]+1} {LATCH[1]} {LATCH[2]} minecraft:redstone_block",
            f"/setblock {LATCH[0]} {LATCH[1]} {LATCH[2]+1} minecraft:redstone_block",
        ))
        world.step_to(world.clock() + 1)
        world.step_to(world.clock() + 1)
        active = (state(world, TOGGLE), state(world, LATCH))
        if not all("powered=true" in value for value in active):
            raise RuntimeError(f"Rear inputs did not activate both latches: {active}")
        if "powered_side=true" not in active[1]:
            raise RuntimeError(f"Side input did not activate Powered Latch side state: {active[1]}")

        world.command("/save-all flush")
        world.restart()
        reopened_active = (state(world, TOGGLE), state(world, LATCH))
        if reopened_active != active:
            raise RuntimeError(f"Active latch state/connection changed across reopen: {active} -> {reopened_active}")

        # Remove only the rear sources. The toggle stays latched; the powered latch
        # follows its remaining side input and then resets when that input is removed.
        world.commands((
            f"/setblock {TOGGLE[0]+1} {TOGGLE[1]} {TOGGLE[2]} minecraft:air",
            f"/setblock {LATCH[0]+1} {LATCH[1]} {LATCH[2]} minecraft:air",
        ))
        world.step_to(world.clock() + 1)
        world.step_to(world.clock() + 1)
        after_rear = (state(world, TOGGLE), state(world, LATCH))
        if "powered=false" not in after_rear[0] or "powering=false" not in after_rear[0]:
            raise RuntimeError(f"Toggle Latch did not retain its latched output after input removal: {after_rear[0]}")
        if "powered=false" not in after_rear[1] or "powered_side=true" not in after_rear[1]:
            raise RuntimeError(f"Powered Latch did not follow its remaining side input: {after_rear[1]}")
        world.command(f"/setblock {LATCH[0]} {LATCH[1]} {LATCH[2]+1} minecraft:air")
        world.step_to(world.clock() + 1)
        world.step_to(world.clock() + 1)
        settled = state(world, LATCH)
        if not all(token in settled for token in ("powered=false", "powered_side=false", "powering=false")):
            raise RuntimeError(f"Powered Latch failed to reset after both input paths were removed: {settled}")

    print("Idle and active latch states survived save/reopen; saved rear/side connections resumed and reset correctly after input removal.")


if __name__ == "__main__":
    main()
