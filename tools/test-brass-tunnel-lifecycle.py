#!/usr/bin/env python3
"""Check Brass Tunnel configuration and buffered cargo across stops and reopen."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world

STRUCTURE = Path("gametest/items/brass_tunnel_split.nbt")
ORIGIN = (3, 96, -12)
TUNNELS = ((6, 98, -11), (6, 98, -10), (6, 98, -9))
LEVER = (5, 98, -10)
SUPPLY = (4, 98, -9)
OUTPUTS = ((10, 97, -11), (10, 97, -10), (10, 97, -9))


def stack_count(nbt):
    return sum(map(int, re.findall(r"\b(?:count|Count): (\d+)", nbt)))


def tunnel_mode(control, pos):
    return int(control.command(f"/data get block {' '.join(map(str, pos))} ScrollValue").split()[-1])


def buffered(control):
    return [stack_count(control.command(
        f"/data get block {' '.join(map(str, pos))} StackToDistribute")) for pos in TUNNELS]


def output_counts(control):
    return [stack_count(control.command(
        f"/data get block {' '.join(map(str, pos))} Items")) for pos in OUTPUTS]


def run(args):
    with fixture_world(args, "Brass-tunnel-lifecycle", STRUCTURE) as control:
        control.command(f"/place template create:gametest/items/brass_tunnel_split {' '.join(map(str, ORIGIN))}")
        for pos in TUNNELS:
            control.command(f"/data merge block {' '.join(map(str, pos))} {{ScrollValue:4}}")
        control.call("save")
        control.restart()
        modes = [tunnel_mode(control, pos) for pos in TUNNELS]
        if modes != [4, 4, 4]:
            raise RuntimeError(f"Idle tunnel mode did not survive save/reopen: {modes}")

        # Reset to split and release the original fixture's ten brass casings.
        for pos in TUNNELS:
            control.command(f"/data merge block {' '.join(map(str, pos))} {{ScrollValue:0}}")
        control.command("/setblock 5 98 -10 minecraft:lever[face=floor,facing=south,powered=false]")
        start = control.clock()
        for tick in range(1, 19):
            control.step_to(start + tick)
        before = buffered(control)
        if sum(before) != 10:
            raise RuntimeError(f"Fixture did not load ten items into the tunnel group: {before}")

        # A stopped belt must retain the buffered stack through another cold reopen.
        control.command(f"/setblock {' '.join(map(str, LEVER))} minecraft:lever[face=floor,facing=south,powered=true]")
        control.step_to(start + 19)
        control.call("save")
        control.restart()
        after = buffered(control)
        if sum(after) != 10 or output_counts(control) != [0, 0, 0]:
            raise RuntimeError(f"Stopped tunnel cargo changed across save/reopen: {after}")

        control.command(f"/setblock {' '.join(map(str, LEVER))} minecraft:lever[face=floor,facing=south,powered=false]")
        resumed = control.clock()
        for tick in range(1, 62):
            control.step_to(resumed + tick)
        remaining = buffered(control)
        outputs = output_counts(control)
        supplied = stack_count(control.command(f"/data get block {' '.join(map(str, SUPPLY))} Items"))
        if sum(remaining) or supplied or sum(outputs) != 10:
            belts = [control.command(f"/data get block {6} 97 {z} Inventory.Items")
                     for z in (-11, -10, -9)]
            motor = control.command("/data get block 5 97 -11")
            raise RuntimeError(
                f"Restarted tunnel did not conserve and distribute all ten items: "
                f"supply={supplied}, buffered={remaining}, outputs={outputs}, "
                f"belts={belts}, motor={motor}"
            )
    print("Idle group modes and ten buffered items survived save/reopen; stopped belt resumed and delivered all ten.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())


if __name__ == "__main__":
    main()
