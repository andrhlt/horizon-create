#!/usr/bin/env python3
"""Process one gold and one copper ingot through the Mechanical Press."""

import argparse
from importlib import import_module
from pathlib import Path

from fixture_world import fixture_world

press = import_module("test-depot-pressing")
ROUTES = (
    ("gold", "minecraft:gold_ingot", "create:golden_sheet", "5 106 -11", "4 106 -11", "5 104 -11"),
    ("copper", "minecraft:copper_ingot", "create:copper_sheet", "13 106 -11", "12 106 -11", "13 104 -11"),
)


def run(args):
    with fixture_world(args, "PressGoldCopper", pack=args.pack) as control:
        for _, _, _, press_pos, motor_pos, depot_pos in ROUTES:
            control.commands((
                f"/setblock {motor_pos} create:creative_motor[facing=east]",
                f"/data merge block {motor_pos} {{ScrollValue:128}}",
                f"/setblock {press_pos} create:mechanical_press[facing=east]",
                f"/setblock {depot_pos} create:depot",
            ))
        control.step_to(control.clock() + 1)
        for _, ingot, _, _, _, depot_pos in ROUTES:
            control.command(f"/item replace block {depot_pos} container.0 with {ingot} 1")

        for _ in range(60):
            done = True
            for name, ingot, sheet, _, _, depot_pos in ROUTES:
                response = control.command(f"/data get block {depot_pos}")
                counts = press.item_counts(response, ingot, sheet)
                if counts[0] != 0 or counts[1] + counts[2] != 1:
                    done = False
            if done:
                break
            control.step_to(control.clock() + 1)
        else:
            raise RuntimeError("Gold and copper Press routes did not both finish within 60 ticks.")

        for name, ingot, sheet, _, _, depot_pos in ROUTES:
            response = control.command(f"/data get block {depot_pos}")
            counts = press.item_counts(response, ingot, sheet)
            if counts[0] != 0 or counts[1] + counts[2] != 1:
                raise RuntimeError(f"{name} route expected one {sheet} and no {ingot}, got {response}")
    print("One gold ingot became one golden sheet and one copper ingot became one copper sheet.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
