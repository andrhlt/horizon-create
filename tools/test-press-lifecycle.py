#!/usr/bin/env python3
"""Check Mechanical Press output overflow and idle/active world reopen."""

import argparse
from importlib import import_module
from pathlib import Path
import re

from fixture_world import fixture_world

press = import_module("test-depot-pressing")
PRESS = "5 106 -11"
DEPOT = "5 104 -11"
IRON = "minecraft:iron_ingot"
SHEET = "create:iron_sheet"


def setup(control, input_count=0):
    press.power_on(control)
    control.command(f"/setblock {PRESS} create:mechanical_press[facing=east]")
    control.command(f"/setblock {DEPOT} create:depot")
    control.step_to(control.clock() + 1)
    if input_count:
        control.command(f"/item replace block {DEPOT} container.0 with {IRON} {input_count}")


def block(control, pos):
    return control.command(f"/data get block {pos}")


def press_state(control):
    nbt = block(control, PRESS)
    return tuple(press.scalar(nbt, key) for key in ("Speed", "Running", "Mode", "Ticks"))


def depot_counts(control):
    return press.item_counts(block(control, DEPOT), IRON, SHEET)


def dropped_sheets(control):
    return sum(entity["item"]["count"] for entity in control.call("entities", 128, "minecraft:item")["entities"]
               if entity["item"]["item"] == SHEET)


def wait_until(control, predicate, description, timeout=100):
    for _ in range(timeout):
        if predicate():
            return
        control.step_to(control.clock() + 1)
    raise RuntimeError(f"Timed out waiting for {description}.")


def full_output(args):
    with fixture_world(args, "PressFullOutput", pack=args.pack) as control:
        setup(control)
        slots = [f'{{Slot:0b,id:"{IRON}",count:2}}']
        slots.extend(f'{{Slot:{slot}b,id:"minecraft:cobblestone",count:64}}' for slot in range(1, 9))
        control.command(f"/data merge block {DEPOT} {{Items:[{','.join(slots)}]}}")
        wait_until(control, lambda: depot_counts(control)[0] == 0 and not press.scalar(block(control, PRESS), "Running"),
                   "the two-item press input to finish")
        ingots, stored_sheets, buffered = depot_counts(control)
        stone = re.search(r'Items: \[([^]]*)\]', block(control, DEPOT))
        stone_count = sum(press.scalar(stack, "count", 0)
                          for stack in re.findall(r"\{([^{}]*)\}", stone[1] if stone else "")
                          if 'id: "minecraft:cobblestone"' in stack)
        dropped = dropped_sheets(control)
        total_sheets = stored_sheets + buffered + dropped
        if (ingots, total_sheets, stone_count) != (0, 2, 512):
            raise RuntimeError(
                f"Full Depot lost or duplicated Press output: ingots={ingots}, sheets={total_sheets}, "
                f"cobblestone={stone_count}, dropped={dropped}, depot={block(control, DEPOT)}, "
                f"items={control.call('entities', 128, 'minecraft:item')['entities']}"
            )


def persistence(args):
    with fixture_world(args, "PressIdleReopen", pack=args.pack) as control:
        setup(control)
        before = (press_state(control), depot_counts(control))
        if before[0][0] != 128 or before[0][1] != 0:
            raise RuntimeError(f"Unexpected idle powered Press state: {before}")
        control.restart()
        after = (press_state(control), depot_counts(control))
        if after != before:
            raise RuntimeError(f"Idle Press state changed after reopen: before={before}, after={after}")

    with fixture_world(args, "PressActiveReopen", pack=args.pack) as control:
        setup(control, input_count=2)
        wait_until(control, lambda: press_state(control)[1] == 1 and press_state(control)[3] >= 30,
                   "active Press progress before save")
        before = (press_state(control), depot_counts(control))
        control.restart()
        after = (press_state(control), depot_counts(control))
        conserved_before = sum(before[1]) + dropped_sheets(control)
        conserved_after = sum(after[1]) + dropped_sheets(control)
        if (after[0][0] != before[0][0] or after[0][1] != 1 or after[0][3] <= 0
                or conserved_after != conserved_before):
            raise RuntimeError(f"Active Press input/progress changed after reopen: before={before}, after={after}")
        wait_until(control, lambda: depot_counts(control)[0] == 0 and not press_state(control)[1],
                   "active Press cycle to finish after reopen")
        ingots, sheets, buffered = depot_counts(control)
        if ingots or sheets + buffered != 2:
            raise RuntimeError(f"Press failed to resume both inputs after reopen: {depot_counts(control)}")


def run(args):
    full_output(args)
    persistence(args)
    print("Full Depot output retained two sheets without duplication; idle and active Press state survived reopen, and active processing resumed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
