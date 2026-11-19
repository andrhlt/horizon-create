#!/usr/bin/env python3
"""Compare real Mechanical Press and Mixer placement with Java."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
PRESS = "create:mechanical_press"
MIXER = "create:mechanical_mixer"
FACING = r"\bfacing=([a-z]+)"
SIDES = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
CASES = {
    "empty_north": (0, ()), "empty_east": (90, ()),
    "empty_south": (180, ()), "empty_west": (270, ()),
    "north_shaft": (90, ("north",)), "east_shaft": (0, ("east",)),
    "south_shaft": (90, ("south",)), "west_shaft": (0, ("west",)),
    "opposed_z": (90, ("north", "south")), "opposed_x": (0, ("east", "west")),
    "crossed_north_east": (180, ("north", "east")),
    "sneaking_side": (0, ("west",)),
}
SURFACES = {
    "over_basin": "create:basin",
    "over_depot": "create:depot",
    "over_ejector": "create:weighted_ejector",
    "over_flat_belt": "create:belt[facing=east,part=middle,slope=horizontal]",
    "over_up_belt": "create:belt[facing=east,part=middle,slope=upward]",
    "blocked_basin": "create:basin",
}


def at(pos):
    return " ".join(map(str, pos))


def try_placement(control, index, name, item):
    x, z = 5 + 5 * (index % 6), -11 + 5 * (index // 6)
    target, support, upper = (x, 106, z), (x, 105, z), (x, 107, z)
    yaw, shafts = CASES.get(name, (90, ()))
    surface = SURFACES.get(name, "minecraft:stone")
    blocked = name == "blocked_basin"
    blocker = "minecraft:stone" if blocked else "minecraft:air"
    if name in SURFACES:
        player_x, player_z = x + 2, z
        feet = 105 if blocked else 106
    else:
        dx, dz = {0: (0, -2), 90: (2, 0), 180: (0, 2), 270: (-2, 0)}[yaw]
        player_x, player_z = x + dx, z + dz
        feet = 108
    control.commands((
        f"/setblock {player_x} {feet-1} {player_z} minecraft:smooth_stone",
        f"/setblock {at(target)} minecraft:air",
        f"/setblock {at(upper)} {blocker}",
        f"/setblock {at(support)} {surface}",
        *(f"/setblock {x+SIDES[side][0]} 106 {z+SIDES[side][1]} "
          f"create:shaft[axis={'z' if side in ('north', 'south') else 'x'}]" for side in shafts),
        f"/tp @s {player_x+.5} {feet} {player_z+.5} {yaw} 0",
        f"/clear @s {item}",
        f"/give @s {item}",
    ))
    control.step_to(control.clock() + 1)
    multiplayer.until("Press available", lambda: multiplayer.count(control, item) == 1)
    control.call("select", item)
    selected = control.call("block", *support)["state"]
    if not selected.startswith(surface.partition("[")[0]):
        raise RuntimeError(f"Expected {surface}, got {selected}")
    sneaking = item == MIXER or name == "sneaking_side" or name in SURFACES
    if sneaking:
        control.call("key", "shift", "down")
        control.step_to(control.clock() + 1)
    try:
        control.call("interact", *support, "up")
    finally:
        if sneaking:
            control.call("key", "shift", "up")
    control.call("wait", 2)
    control.clock()
    count = multiplayer.count(control, item)
    for height, position in enumerate((target, upper), 1):
        state = control.call("block", *position)["state"]
        if state.partition("[")[0] == item:
            facing = re.search(FACING, state)
            return facing[1] if facing else "-", count, height
    return "-", count, 0


def run(args):
    item = MIXER if args.mixer else PRESS
    device = "Mixer" if args.mixer else "Press"
    reference = args.reference or ROOT / f"fixtures/{device.lower()}-placement-java.csv"
    with reference.open() as file:
        expected = list(csv.DictReader(file))
    differences = []
    with fixture_world(args, f"{device}Placement", render=True, pack=args.pack) as control:
        control.command("/gamemode survival")
        for index, case in enumerate(expected):
            name = case["case"]
            try:
                actual = try_placement(control, index, name, item)
            except RuntimeError as error:
                raise RuntimeError(f"{device} placement {name}: {error}") from error
            wanted = (case["facing"], int(case["held"]), int(case["height"]))
            if actual != wanted:
                differences.append((name, wanted, actual))
    if differences:
        raise RuntimeError(f"{device} placement differs from Java: {differences}")
    print(f"All {len(expected)} Java {device} placement and item consumption cases matched.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--mixer", action="store_true")
    run(parser.parse_args())
