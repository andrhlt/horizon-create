#!/usr/bin/env python3
"""Check survival placement and rear-shaft RPM for both Create cuckoo clocks."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world

VARIANTS = ("create:cuckoo_clock", "create:mysterious_cuckoo_clock")
TARGETS = ((8, 180, 20), (14, 180, 20))


def speed(text):
    match = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)f\b", text)
    if match is None:
        raise RuntimeError(f"Missing kinetic Speed in {text}")
    return float(match.group(1))


def run(args):
    with fixture_world(args, "CuckooClockVariants", render=False, pack=args.pack,
                       env={"HORIZON_NO_AUDIO": "1"}) as host:
        host.commands((
            "/fill 6 179 17 16 179 24 minecraft:stone",
            "/fill 6 180 17 16 184 24 minecraft:air",
            "/gamemode survival",
        ))
        for index, (block, pos) in enumerate(zip(VARIANTS, TARGETS)):
            x, y, z = pos
            # Place the block in ordinary survival first, then connect a motor
            # and shaft through the rear of its actual facing.
            host.commands((
                f"/item replace entity @s hotbar.0 with {block} 1",
                f"/tp @s {x + 0.5} {y} {z + 3.5}",
            ))
            host.call("select", block)
            host.call("look-at", x + 0.5, y + 0.5, z + 0.5)
            host.call("wait", 3)
            host.call("interact", x, y - 1, z, "up")
            state = host.call("block", *pos)["state"]
            if not state.startswith(f"{block}["):
                raise RuntimeError(f"Survival placement of {block} produced {state}")
            if host.call("inventory")["counts"].get(block, 0) != 0:
                raise RuntimeError(f"Survival placement did not consume the {block} item")
            facing = re.search(r"\bfacing=(north|south|east|west)", state)
            if facing is None:
                raise RuntimeError(f"No horizontal facing in placed state {state}")
            rear = {"north": (0, 0, 1), "south": (0, 0, -1),
                    "east": (-1, 0, 0), "west": (1, 0, 0)}[facing.group(1)]
            dx, dy, dz = rear
            host.commands((
                f"/setblock {x + dx} {y + dy} {z + dz} create:shaft[axis={'x' if dx else 'z'}]",
                f"/setblock {x + 2 * dx} {y + 2 * dy} {z + 2 * dz} create:creative_motor[facing={'east' if dx < 0 else 'west' if dx > 0 else 'south' if dz < 0 else 'north'}]",
                f"/data merge block {x + 2 * dx} {y + 2 * dy} {z + 2 * dz} {{ScrollValue:16}}",
            ))
            # Confirm this clock joins the motor network through its rear face.
            host.step_to(host.clock() + 1)
            host.step_to(host.clock() + 1)
            observed = speed(host.command(f"/data get block {x} {y} {z}"))
            if observed != 16:
                raise RuntimeError(f"{block} rear shaft expected 16 RPM, got {observed}")
            print(f"{block}: placed as {state}; rear shaft {observed:g} RPM", flush=True)
    print("Both cuckoo clock variants placed in survival and ran at 16 RPM from the rear shaft.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, required=True)
    run(parser.parse_args())
