#!/usr/bin/env python3
"""Check pulse diode configuration and active operation across world reopen."""
import argparse
from pathlib import Path
import re

from fixture_world import fixture_world
from importlib import import_module

state_properties = import_module("test-stone-palettes").state_properties

POSITIONS = {
    "pulse_extender": (8, 120, -8),
    "pulse_repeater": (8, 124, -8),
    "pulse_timer": (8, 128, -8),
}


def coords(pos):
    return " ".join(map(str, pos))


def nbt(world, pos):
    return world.command(f"/data get block {coords(pos)}")


def number(data, key):
    match = re.search(rf"\b{key}: (-?\d+)", data)
    if not match:
        raise RuntimeError(f"Missing {key} in diode data: {data}")
    return int(match[1])


def block_state(world, pos):
    return world.call("block", *pos)["state"]


def setup_idle(world):
    commands = ["/fill 5 119 -10 11 131 -5 minecraft:smooth_stone"]
    for block, pos in POSITIONS.items():
        interval = 200
        commands.extend((
            f"/setblock {coords(pos)} create:{block}[facing=east,inverted=true]{{State:0,ScrollValue:{interval}}}",
            f"/setblock {pos[0]-1} {pos[1]} {pos[2]} minecraft:redstone_wire[power=0]",
            f"/setblock {pos[0]} {pos[1]} {pos[2]-1} minecraft:redstone_wire[power=0]",
        ))
    world.commands(commands)


def assert_config(world, expected):
    for block, pos in POSITIONS.items():
        data = nbt(world, pos)
        interval, flags_want = expected[block]
        flags = state_properties(block_state(world, pos))
        got = (number(data, "ScrollValue"), flags.get("inverted"))
        if got != (interval, flags_want):
            raise RuntimeError(f"Idle {block} interval/polarity changed across reopen: expected {(interval, flags_want)}, got {got}; {data}")


def active_samples(world):
    samples = {}
    for block, pos in POSITIONS.items():
        data = nbt(world, pos)
        state = block_state(world, pos)
        samples[block] = (number(data, "State"), number(data, "ScrollValue"), state)
    return samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()

    artifacts = Path(".local/app-2036-pulse-diodes")
    with fixture_world(args, "BrassDiodePersistence", render=False, pack=args.pack,
                       artifact_dir=artifacts) as world:
        setup_idle(world)
        expected = {block: (200, "true") for block in POSITIONS}
        world.command("/save-all flush")
        world.restart()
        assert_config(world, expected)

        for block, pos in POSITIONS.items():
            world.command(f"/setblock {pos[0]+1} {pos[1]} {pos[2]} minecraft:redstone_block")
        world.step_to(world.clock() + 1)
        world.step_to(world.clock() + 1)
        before = active_samples(world)
        if not any(sample[0] > 0 or "powering=true" in sample[2] for sample in before.values()):
            raise RuntimeError(f"Input did not activate any diode before save: {before}")
        world.command("/save-all flush")
        world.restart()
        reopened = active_samples(world)
        for block in POSITIONS:
            before_state, before_interval, before_flags = before[block]
            after_state, after_interval, after_flags = reopened[block]
            if (after_state < before_state or after_interval != before_interval
                    or state_properties(before_flags) != state_properties(after_flags)):
                raise RuntimeError(f"Active {block} configuration regressed across reopen: {before[block]} -> {reopened[block]}")
        world.step_to(world.clock() + 1)
        resumed = active_samples(world)
        if all(resumed[block][0] == reopened[block][0] for block in POSITIONS):
            raise RuntimeError(f"Active diode operation did not resume after reopen: {reopened}")

    print("Pulse Extender, Repeater, and Timer idle settings survived save/reopen; active input state was retained and operation resumed.")


if __name__ == "__main__":
    main()
