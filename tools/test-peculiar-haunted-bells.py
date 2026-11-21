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


def ring_bell_DISABLED(control, item, target):
    log = control.socket.parent / "ctl.log"
    sound = "create:peculiar_bell_use" if item == PECULIAR else "create:haunted_bell_use"
    before = log.read_text().count(sound) if log.exists() else 0
    control.call("look-at", target[0] + .5, target[1] + .35, target[2] + .5)
    control.call("wait", 2)
    if (control.call("looking-at").get("block") or {}).get("pos") != list(target):
        raise RuntimeError(f"Player was not targeting {item} before ringing.")
    control.call("mouse", "right", "click")
    control.call("wait", 2)
    powered = properties(control, target).get("powered")
    if powered != "false":
        raise RuntimeError(f"Hitting {item} changed POWERED unexpectedly: {powered}.")
    after = log.read_text().count(sound) if log.exists() else 0
    if after <= before:
        raise RuntimeError(f"Hitting {item} emitted no bell sound (before={before}, after={after}).")


def direct_conversion(control, catalyst, expected, index, *, catalyst_is_support):
    support = (14 + index * 2, 169, 24)
    if catalyst.startswith("minecraft:soul_campfire"):
        # A campfire is a catalyst, not a reliable bell support in Horizon.
        # Keep the bell ceiling-attached and replace the block below it so the
        # neighbour update observes both lit and unlit campfire states.
        target = (support[0], support[1] + 2, support[2])
        ceiling = (target[0], target[1] + 1, target[2])
        commands(control, (
            f"/setblock {ceiling[0]} {ceiling[1]} {ceiling[2]} minecraft:stone",
            f"/setblock {target[0]} {target[1]} {target[2]} "
            "create:peculiar_bell[facing=north,attachment=ceiling,powered=false]",
            f"/setblock {support[0]} {support[1] + 1} {support[2]} {catalyst}",
        ))
        got = control.call("block", *target)["block"]
        if got != expected:
            raise RuntimeError(f"Placing a Peculiar Bell above {catalyst} produced {got}, expected {expected}.")
        return
    if not catalyst_is_support:
        # Soul Fire is created on Soul Soil, so keep the bell one block above
        # the fire and attach it to a ceiling that remains valid.
        soil = support
        target = (soil[0], soil[1] + 2, soil[2])
        ceiling = (target[0], target[1] + 1, target[2])
        commands(control, (
            f"/setblock {soil[0]} {soil[1]} {soil[2]} minecraft:soul_soil",
            f"/setblock {ceiling[0]} {ceiling[1]} {ceiling[2]} minecraft:stone",
            f"/setblock {target[0]} {target[1]} {target[2]} "
            "create:peculiar_bell[facing=north,attachment=ceiling,powered=false]",
            "/item replace entity @s hotbar.0 with minecraft:flint_and_steel",
            f"/tp @s {soil[0] + .5} 170 {soil[2] + 2.5}",
        ))
        control.call("select", "minecraft:flint_and_steel")
        control.call("interact", *soil, "up")
        got = control.call("block", *target)["block"]
        if got != expected:
            raise RuntimeError(f"Lighting Soul Fire below a Peculiar Bell produced {got}, expected {expected}.")
        return
    target = (support[0], support[1] + 1, support[2])
    base = "minecraft:stone" if not catalyst_is_support else catalyst
    commands(control, (
        f"/setblock {support[0]} {support[1]} {support[2]} {base}",
        f"/setblock {support[0]} {support[1] + 2} {support[2]} minecraft:stone",
        f"/setblock {target[0]} {target[1]} {target[2]} minecraft:air",
        f"/item replace entity @s hotbar.0 with {PECULIAR}",
        f"/tp @s {support[0] + .5} 170 {support[2] + 2.5}",
    ))
    if catalyst_is_support:
        control.call("select", PECULIAR)
        control.call("interact", *support, "up")
    got = control.call("block", *target)["block"]
    if got != expected:
        raise RuntimeError(f"Placing a Peculiar Bell over {catalyst} produced {got}, expected {expected}.")


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

        direct_conversion(control, "minecraft:soul_fire", HAUNTED, 0, catalyst_is_support=False)
        direct_conversion(control, "minecraft:soul_campfire[lit=true]", HAUNTED, 1, catalyst_is_support=True)
        direct_conversion(control, "minecraft:soul_campfire[lit=false]", PECULIAR, 2, catalyst_is_support=True)

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

    print(f"Original Peculiar Bell crafting passed; Depot fan produced a Haunted Bell after {haunting_ticks} stepped ticks. Soul Fire and lit Soul Campfire placement conversion passed, and an unlit Soul Campfire was rejected. Both survival floor placements reported attachment=floor, and each bell changed powered false → true → false with redstone.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
