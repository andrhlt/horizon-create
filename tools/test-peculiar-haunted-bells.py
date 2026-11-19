#!/usr/bin/env python3
"""Craft, haunt, place, and power Create's Peculiar and Haunted Bells."""

import argparse
import json
from importlib import import_module
from pathlib import Path
import re

from fixture_world import fixture_world

crafting = import_module("test-machine-crafting")
PECULIAR = "create:peculiar_bell"
HAUNTED = "create:haunted_bell"
DEPOT = (7, 105, -11)


def commands(control, entries):
    control.call("script", script="".join(f"command {json.dumps(item)}\n" for item in entries))


def properties(control, pos):
    state = control.call("block", *pos)["state"]
    return dict(re.findall(r"(\w+)=([\w]+)", state))


def place_floor_bell(control, item, support, target, redstone):
    commands(control, (
        f"/item replace entity @s hotbar.0 with {item}",
        "/gamemode survival",
        f"/tp @s {support[0] + .5} {support[1] + 1} {support[2] + 2.5}",
    ))
    control.call("select", item)
    control.call("interact", *support, "up")
    block = control.call("block", *target)
    wanted = {"attachment": "floor", "powered": "false"}
    got = properties(control, target)
    if block["block"] != item or any(got.get(key) != value for key, value in wanted.items()):
        raise RuntimeError(f"Survival placement of {item} gave {block['block']} {got}, expected {wanted}.")

    control.command(f"/setblock {redstone[0]} {redstone[1]} {redstone[2]} minecraft:redstone_block")
    powered = properties(control, target)
    if powered.get("powered") != "true":
        raise RuntimeError(f"Redstone did not power {item}: {powered}.")
    control.command(f"/setblock {redstone[0]} {redstone[1]} {redstone[2]} minecraft:air")
    unpowered = properties(control, target)
    if unpowered.get("powered") != "false":
        raise RuntimeError(f"Removing redstone did not clear {item}: {unpowered}.")


def run(args):
    with fixture_world(args, "Peculiar-haunted-bells", render=True, pack=args.pack) as control:
        commands(control, (
            "/fill 8 169 22 16 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))

        crafting.replay(control, {
            "recipe": "crafting/curiosities/peculiar_bell",
            "width": "1",
            "slots": "create:brass_block,create:brass_sheet",
            "output": PECULIAR,
            "count": "1",
            "remainder": "",
        })
        if control.call("inventory")["counts"].get(PECULIAR) != 1:
            raise RuntimeError("The original brass block and sheet recipe did not produce one Peculiar Bell.")

        place_floor_bell(control, PECULIAR, (9, 169, 24), (9, 170, 24), (8, 170, 24))

        # Mirror Create's Depot fan lane: a soul campfire supplies the haunting
        # catalyst, with the fan pushing east into the Depot.
        commands(control, (
            "/setblock 4 106 -11 create:creative_motor[facing=east]",
            "/data merge block 4 106 -11 {ScrollValue:256}",
            "/setblock 5 106 -11 create:encased_fan[facing=east]",
            "/setblock 6 105 -11 minecraft:stone",
            "/setblock 6 106 -12 minecraft:stone",
            "/setblock 6 106 -10 minecraft:stone",
            "/setblock 7 106 -11 minecraft:oak_sign",
            "/setblock 6 106 -11 minecraft:soul_campfire[lit=true]",
            "/setblock 7 105 -11 create:depot",
        ))
        start = control.clock()
        for tick in range(1, 6):
            control.step_to(start + tick)
        control.command(f"/item replace block {DEPOT[0]} {DEPOT[1]} {DEPOT[2]} container.0 with {PECULIAR}")

        result = None
        haunting_ticks = None
        last_depot = ""
        for tick in range(1, 181):
            control.step_to(start + 5 + tick)
            depot = control.command(f"/data get block {DEPOT[0]} {DEPOT[1]} {DEPOT[2]}")
            last_depot = depot
            if HAUNTED in depot:
                result = depot
                haunting_ticks = tick
                break
        if result is None:
            fan = control.command("/data get block 5 106 -11")
            raise RuntimeError(f"The powered Depot fan did not haunt the Peculiar Bell within 180 ticks; fan: {fan}; Depot: {last_depot}")
        if PECULIAR in result:
            raise RuntimeError(f"Haunting left the Peculiar Bell in the Depot: {result}")
        control.command(f"/item replace entity @s hotbar.0 with {HAUNTED}")
        place_floor_bell(control, HAUNTED, (11, 169, 24), (11, 170, 24), (12, 170, 24))

    print(f"Original Peculiar Bell crafting passed; Depot fan produced a Haunted Bell after {haunting_ticks} stepped ticks. Both survival floor placements reported attachment=floor, and each bell changed powered false → true → false with redstone.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
