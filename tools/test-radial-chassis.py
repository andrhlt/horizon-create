#!/usr/bin/env python3
"""Replay Radial Chassis placement, adhesive and powered bearing against Java Create."""

import argparse
import csv
from pathlib import Path
import re
from runpy import run_path

from fixture_world import ROOT, fixture_world

linear = run_path(str(ROOT / "tools/test-linear-chassis.py"))
AXES = linear["AXES"]
coordinates = linear["coordinates"]
offset = linear["offset"]
property_value = linear["property_value"]
moved_payload = linear["moved_payload"]
check_removed = linear["check_removed"]

RADIAL = "create:radial_chassis"
AIR = "minecraft:air"
SIDES = {
    "east": (1, 0, 0), "west": (-1, 0, 0),
    "up": (0, 1, 0), "down": (0, -1, 0),
    "north": (0, 0, -1), "south": (0, 0, 1),
}
STICKY = {
    "x": {"up": "north", "down": "south", "south": "east", "north": "west"},
    "y": {side: side for side in ("north", "south", "east", "west")},
    "z": {"up": "north", "down": "south", "east": "east", "west": "west"},
}


def read_fixture(name):
    with (ROOT / f"fixtures/radial-chassis{name}-java.csv").open() as file:
        reader = csv.reader(file)
        return next(reader), list(reader)


def compare(name, header, java, actual):
    output = ROOT / f".local/radial-chassis{name}-horizon.csv"
    with output.open("w") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    mismatches = [(expected, observed) for expected, observed in zip(java, actual, strict=True)
                  if expected != observed]
    if mismatches:
        raise RuntimeError(f"Radial Chassis differed (Java, Horizon): {mismatches}")


def chassis(axis, side=None):
    return f"{RADIAL}[axis={axis}" + (f",sticky_{STICKY[axis][side]}=true]" if side else "]")


def assembly_fixture(scenario):
    anchor = (8, 192, 40)
    axle, first, bend = (AXES[(scenario + step) % 3] for step in range(3))
    axis, next_axis = ("xyz"[(scenario + step) % 3] for step in range(2))
    facing, first_face, bent_face = (next(name for name, vector in SIDES.items() if vector == direction)
                                   for direction in (axle, first, tuple(-v for v in bend)))
    neighbor = offset(anchor, axle)
    bearing, motor = offset(anchor, axle, -1), offset(anchor, axle, -2)
    build = {
        anchor: chassis(axis, first_face if scenario % 3 != 0 or scenario == 3 else None),
        neighbor: chassis(axis, bent_face if scenario >= 3 else None),
        offset(neighbor, axle): chassis(next_axis),
        **{offset(anchor, first, length): "minecraft:stone" for length in range(1, 10)},
        offset(anchor, bend): "minecraft:bricks",
    }
    if scenario <= 3:
        build[offset(offset(anchor, first), bend)] = "minecraft:oak_planks"
        build[offset(anchor, bend, 2)] = "minecraft:dirt"
        build[offset(offset(anchor, first, 2), bend, 2)] = "minecraft:cobblestone"
    else:
        at_cutoff = offset(anchor, first, 8)
        build.update({offset(at_cutoff, bend, i): state for i, state in enumerate(
            ("minecraft:smooth_stone", "minecraft:bricks", "minecraft:oak_planks"), start=1
        )})
    build[offset(neighbor, bend, -1)] = "minecraft:oak_planks"
    build[offset(offset(neighbor, bend, -1), first)] = "minecraft:bricks"
    build[offset(neighbor, first)] = "minecraft:dirt"
    return anchor, neighbor, bearing, motor, facing, first_face, bent_face, build


def assemblies(args):
    header, java = read_fixture("")
    actual = []
    for before, moving, after in zip(java[::3], java[1::3], java[2::3], strict=True):
        scenario = int(before[0])
        anchor, neighbor, bearing, motor, facing, first_face, bent_face, build = assembly_fixture(scenario)
        with fixture_world(args, f"radial-chassis-{scenario}", pack=args.pack) as control:
            control.commands((
                "/tp @s 12.5 192 44.5",
                *(f"/setblock {coordinates(pos)} {state}" for pos, state in build.items()),
                f"/setblock {coordinates(bearing)} create:mechanical_bearing[facing={facing}]",
                f"/setblock {coordinates(motor)} create:creative_motor[facing={facing}]{{ScrollValue:0}}",
            ))
            for _ in range(2):
                control.step_to(control.clock() + 1)
            state = {pos: control.call("block", *pos)["state"] for pos in build}
            axis = property_value(state[anchor], "axis")
            coats = [axis, property_value(state[anchor], f"sticky_{STICKY[axis][first_face]}"),
                     property_value(state[neighbor], f"sticky_{STICKY[axis][bent_face]}")]
            actual.append([str(scenario), "0", *coats, "-"])
            start = control.clock()
            control.command(f"/data merge block {coordinates(motor)} {{ScrollValue:16}}")
            control.step_to(start + 1)
            payload = moved_payload(control, bearing, moving[-1])
            check_removed(control, anchor, scenario, build, moving[-1])
            actual.append([str(scenario), "1", "-", "-", "-", payload])
            control.command(f"/data merge block {coordinates(motor)} {{ScrollValue:0}}")
            control.step_to(start + 2)
            restored = control.commands(
                f"/execute if block {coordinates(pos)} {value}" for pos, value in state.items()
            )
            mismatched = [(pos, value) for (pos, value), result in zip(state.items(), restored, strict=True)
                          if "Test passed" not in result]
            if mismatched:
                raise RuntimeError(f"Radial Chassis scenario {scenario} failed to restore: {mismatched}")
            actual.append([str(scenario), "2", *coats, "-"])
    compare("", header, java, actual)
    print(f"Radial Chassis matched all {len(actual)} Java ticks across {len(actual) // 3} bearing assemblies.")


def player(args):
    _, placements = read_fixture("-placement")
    header, java = read_fixture("-adhesive")
    actual = []
    target = (8, 184, 40)
    approach = {
        "east": "/tp @s 11.5 184 40.5 90 20",
        "south": "/tp @s 8.5 184 43.5 180 20",
        "up": "/tp @s 10.5 186 41.5 90 55",
    }
    with fixture_world(args, "radial-chassis-player", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 5 183 37 13 183 44 minecraft:smooth_stone",
            "/setblock 10 185 41 minecraft:smooth_stone",
            f"/item replace entity @s hotbar.0 with {RADIAL} 3",
            "/item replace entity @s hotbar.1 with minecraft:slime_ball 2",
            "/gamemode survival",
        ))
        for index, (axial, glue_side) in enumerate((("east", "up"), ("up", "south"), ("south", "east"))):
            support = offset(target, SIDES[axial], -1)
            support_axis = "xyz"[(index + 1) % 3]
            control.command(f"/setblock {coordinates(support)} create:linear_chassis[axis={support_axis}]")
            control.command(approach[axial])
            control.call("select", RADIAL)
            control.call("wait", 3)
            control.call("interact", *support, axial)
            placed = control.call("block", *target)["state"]
            if not placed.startswith(RADIAL + "[") or property_value(placed, "axis") != placements[index][1]:
                raise RuntimeError(f"Radial placement {index} differed: {placed}.")
            control.call("select", "minecraft:slime_ball")
            for step in range(4):
                face = axial if step == 0 else glue_side
                if step == 1:
                    control.command(approach[face])
                    control.call("wait", 3)
                if step < 3:
                    control.call("interact", *target, face)
                else:
                    control.call("select", 3)
                    control.call("key", "shift", "down")
                    try:
                        control.call("wait", 4)
                        hit = [n + 0.5 + normal * 0.5 for n, normal in zip(target, SIDES[face], strict=True)]
                        control.call("look-at", *hit)
                        control.call("mouse", "right", "click")
                        control.call("wait", 3)
                    finally:
                        control.call("key", "shift", "up")
                state = control.call("block", *target)["state"]
                properties = "|".join(f"{key}={property_value(state, key)}" for key in (
                    "sticky_east", "sticky_north", "sticky_south", "sticky_west"
                ))
                remaining = control.call("inventory")["counts"].get("minecraft:slime_ball", 0)
                actual.append([str(index), str(step), properties, str(remaining)])
            control.command(f"/setblock {coordinates(target)} minecraft:air")
        if control.call("inventory")["counts"].get(RADIAL, 0):
            raise RuntimeError("Survival placement failed to consume three Radial Chassis blocks.")
    compare("-adhesive", header, java, actual)
    print(f"Radial Chassis matched {len(placements)} survival placements and {len(actual)} Java adhesive actions.")


def spin(args):
    anchor, bearing, motor = (8, 194, 24), (8, 193, 24), (8, 192, 24)
    header, java = read_fixture("-spin")
    actual = []
    with fixture_world(args, "radial-chassis-spin", pack=args.pack) as control:
        control.commands((
            "/tp @s 10.5 194 26.5",
            f"/setblock {coordinates(anchor)} {chassis('y', 'east')}",
            f"/setblock {coordinates(offset(anchor, SIDES['east']))} minecraft:bricks",
            f"/setblock {coordinates(bearing)} create:mechanical_bearing[facing=up]",
            f"/setblock {coordinates(motor)} create:creative_motor[facing=up]{{ScrollValue:0}}",
        ))
        start = control.clock()
        for row in java:
            tick = int(row[0])
            if tick:
                control.step_to(start + tick)
            data = control.command(f"/data get block {coordinates(bearing)}")
            angle = float(result[1]) if (result := re.search(r"\bAngle: (-?[\d.]+)f", data)) else 0.0
            moving = re.search(r"\bRunning: 1[b,}]", data) is not None
            coats = []
            bricks = []
            if not moving:
                planar = ("east", "north", "south", "west")
                states = control.commands((
                    *(f"/execute if block {coordinates(anchor)} {chassis('y', side)}" for side in planar),
                    *(f"/execute if block {coordinates(offset(anchor, SIDES[side]))} minecraft:bricks" for side in planar),
                ))
                coats = [f"sticky_{side}" for side, result in zip(planar, states[:4], strict=True)
                         if "Test passed" in result]
                bricks = [side for side, result in zip(planar, states[4:], strict=True) if "Test passed" in result]
            actual.append([str(tick), f"{angle:.3f}", str(moving).lower(), "|".join(coats), "|".join(bricks)])
            if tick in (3, 23):
                speed = 16 if tick == 3 else 0
                control.command(f"/data merge block {coordinates(motor)} {{ScrollValue:{speed}}}")
    compare("-spin", header, java, actual)
    print(f"Radial Chassis matched {len(actual)} Java ticks of bearing angle, rotation and remapped sticky faces.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=lambda name: Path(name).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--player", action="store_true")
    modes.add_argument("--spin", action="store_true")
    args = parser.parse_args()
    (player if args.player else spin if args.spin else assemblies)(args)
