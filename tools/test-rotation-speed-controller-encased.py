#!/usr/bin/env python3
"""Compare controller placement and transmission with encased cogwheels."""

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

CONTROLLER = "create:rotation_speed_controller"
MOTOR = "create:creative_motor[facing=east]"
CASES = (
    ("brass_encased_large_cogwheel", "x", "z", False, 0),
    ("andesite_encased_large_cogwheel", "z", "x", True, 90),
    ("brass_encased_large_cogwheel", "x", "x", False, None),
    ("andesite_encased_large_cogwheel", "y", "x", True, 0),
    ("brass_encased_cogwheel", "x", "x", False, 0),
    ("brass_encased_large_cogwheel", "x", "z", False, None),
)


def coords(pos):
    return " ".join(map(str, pos))


@dataclass(frozen=True)
class Rig:
    controller: tuple[int, int, int]
    cog: tuple[int, int, int]
    output: tuple[int, int, int]
    motor: tuple[int, int, int]
    axis: str
    remaining: int


def build_rig(control, case, spec):
    cog, cog_axis, shaft_axis, shaft_drives, yaw = spec
    x, y, z = 8 + case * 4, 101, -10
    base = (x, y, z)
    above = (x, y + 1, z)
    output = (x, y, z + 1) if shaft_axis == "z" else (x + 1, y, z)
    source = (x - 1, y if shaft_drives else y + 1, z)
    open_ends = "false" if shaft_drives else "true"
    control.commands((
        f"/fill {x - 2} {y - 1} {z - 1} {x + 1} {y - 1} {z + 1} minecraft:smooth_stone",
        f"/fill {x - 2} {y} {z - 1} {x + 1} {y + 2} {z + 1} minecraft:air",
        f"/setblock {coords(above)} create:{cog}[axis={cog_axis},top_shaft={open_ends},bottom_shaft={open_ends}]",
    ))
    if yaw is None:
        control.command(f"/setblock {coords(base)} {CONTROLLER}[axis={shaft_axis}]")
        remaining = -1
    else:
        control.commands((
            f"/tp @s {x - 2} {y} {z + 0.5} {yaw} 0",
            f"/item replace entity @s hotbar.0 with {CONTROLLER} 2",
        ))
        control.call("wait", 3)
        control.call("select", CONTROLLER)
        control.call("interact", x, y - 1, z, "up")
        control.call("wait", 2)
        remaining = control.call("inventory")["counts"].get(CONTROLLER, 0)

    state = control.call("block", *base)["state"]
    axis = re.search(r"\baxis=([xz])\b", state)
    if not state.startswith(f"{CONTROLLER}[") or axis is None:
        raise RuntimeError(f"Case {case} did not install a speed controller: {state}")
    control.command(f"/setblock {coords(output)} create:shaft[axis={shaft_axis}]")
    return Rig(base, above, output, source, axis[1], remaining)


def update_motors(control, rigs, speed=None):
    commands = []
    for rig in rigs:
        pos = coords(rig.motor)
        commands.append(f"/setblock {pos} {MOTOR if speed is not None else 'minecraft:air'}")
        if speed is not None:
            commands.append(f"/data merge block {pos} {{ScrollValue:{speed}}}")
    control.commands(commands)


def speed(nbt):
    tag = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)f\b", nbt)
    if tag is None:
        raise RuntimeError(f"Expected kinetic speed in {nbt}")
    return float(tag[1])


def sample(control, rigs, tick):
    readings = iter(control.commands(
        f"/data get block {coords(pos)}"
        for rig in rigs
        for pos in (rig.controller, rig.cog, rig.output)
    ))
    return [
        (str(case), str(tick), rig.axis, str(rig.remaining),
         *(f"{speed(next(readings)):.4f}" for _ in range(3)))
        for case, rig in enumerate(rigs)
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path,
                        default=ROOT / ".local/rotation-speed-controller-encased-horizon.csv")
    args = parser.parse_args()

    with (ROOT / "fixtures/rotation-speed-controller-encased-java.csv").open() as stream:
        header, *rows = list(csv.reader(stream))
    expected = [tuple(row) for row in rows if int(row[1]) > 0]
    actual = []
    with fixture_world(args, "rotation-speed-controller-encased", render=True, pack=args.pack) as control:
        control.command("/gamemode survival")
        rigs = [build_rig(control, case, spec) for case, spec in enumerate(CASES)]
        update_motors(control, rigs, 24)
        start = control.clock()
        for tick in range(1, 13):
            control.step_to(start + tick)
            actual.extend(sample(control, rigs, tick))
            if tick == 4:
                update_motors(control, rigs)
            elif tick == 8:
                update_motors(control, rigs, 32)

    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    if differences:
        raise RuntimeError(f"{len(differences)} encased controller differences. First 12: {differences[:12]}")
    print(f"Encased-cog orientation, survival inventory and both drive directions matched Java for {len(actual)} samples.")


if __name__ == "__main__":
    main()
