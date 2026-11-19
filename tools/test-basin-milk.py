#!/usr/bin/env python3
"""Pour a held milk bucket into a Basin from ordinary survival."""

import argparse
from pathlib import Path
import re

from fixture_world import fixture_world

BASIN = (5, 97, -9)


def run(args):
    with fixture_world(args, "Basin-milk-bucket", render=True, pack=args.pack) as control:
        control.command("/fill 3 96 -11 8 96 -6 minecraft:smooth_stone")
        control.command("/fill 3 97 -11 8 100 -6 minecraft:air")
        control.command("/setblock 5 97 -9 create:basin")
        control.command("/tp @s 3.0 97.0 -8.5 -90 20")
        control.call("wait", 3)
        control.command("/gamemode survival")
        for attempt in range(2):
            control.command("/item replace entity @s hotbar.0 with minecraft:milk_bucket")
            control.call("select", "minecraft:milk_bucket")
            control.call("interact", *BASIN, "up")
            contents = control.command("/data get block 5 97 -9 InputTanks")
            counts = control.call("inventory")["counts"]
            if not re.search(r'id: "minecraft:milk"', contents):
                raise RuntimeError(f"Milk did not reach the basin: {contents}")
            amounts = re.findall(r'\bamount: (\d+)', contents)
            if amounts != ["1000"]:
                raise RuntimeError(f"Expected just one milk bucket in the basin: {contents}")
            expected = ("minecraft:bucket", "minecraft:milk_bucket")[attempt]
            if counts.get(expected, 0) != 1:
                raise RuntimeError(f"Wrong result for milk attempt {attempt + 1}: {counts}")
        control.commands((
            "/setblock 4 98 -9 create:creative_motor[facing=up]",
            "/data merge block 4 98 -9 {ScrollValue:256}",
            "/setblock 4 99 -9 create:cogwheel[axis=y]",
            "/setblock 5 99 -9 create:mechanical_mixer",
            "/setblock 5 96 -9 create:blaze_burner[blaze=kindled]",
            "/data merge block 5 96 -9 {fuelLevel:1,burnTimeRemaining:1600}",
            "/item replace block 5 97 -9 container.0 with minecraft:cocoa_beans 2",
            "/item replace block 5 97 -9 container.1 with minecraft:sugar 2",
        ))
        clock = control.clock()
        for tick in range(1, 81):
            control.step_to(clock + tick)
        remaining, mixed = control.commands((
            "/data get block 5 97 -9 InputTanks",
            "/data get block 5 97 -9 OutputTanks",
        ))
        if not re.search(r'amount: 500\b', remaining) or not re.search(r'amount: 500\b', mixed):
            raise RuntimeError(f"The combined batches should use 500 mB of milk and produce 500 mB of chocolate: {remaining}, {mixed}")
        if 'id: "create:chocolate"' not in mixed:
            raise RuntimeError(f"Expected chocolate from ordinary milk, sugar and cocoa: {mixed}")
    print("Survival milk buckets fill one input tank, return a bucket, and supply liquid chocolate production.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    run(parser.parse_args())
