#!/usr/bin/env python3
"""Replay Java's powered controller rotations and survival Wrench pickup."""

import argparse
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

controller = import_module("test-rotation-speed-controller")
wrench = import_module("test-wrench")
BLOCK = "create:rotation_speed_controller"
POSITION = wrench.POSITION
MOTOR = (8, 180, 22)
SHAFT = (8, 180, 24)
FACES = {3: "up", 5: "west", 7: "down", 9: "west"}


def sample(world, tick):
    name, properties = wrench.state(world.call("block", *POSITION)["state"])
    axis = properties["axis"] if name == BLOCK else "air"
    nbt = world.command(f"/data get block {controller.coords(POSITION)}") if name == BLOCK else None
    setting = controller.tag(nbt, "ScrollValue", int) if nbt is not None else 0
    rpm = controller.tag(nbt, "Speed", float) if nbt is not None else 0
    motor, shaft = world.commands(f"/data get block {controller.coords(pos)}" for pos in (MOTOR, SHAFT))
    speeds = (rpm, controller.tag(motor, "Speed", float), controller.tag(shaft, "Speed", float))
    counts = world.call("inventory")["counts"]
    if counts.get("create:wrench") != 1:
        raise RuntimeError(f"The survival player lost the Wrench at tick {tick}.")
    return (str(tick), axis, str(setting), *(f"{speed:.4f}" for speed in speeds), str(counts.get(BLOCK, 0)))


def verify(args):
    with (ROOT / "fixtures/rotation-speed-controller-wrench-java.csv").open() as stream:
        header, *rows = list(csv.reader(stream))
    expected = [tuple(row) for row in rows if int(row[0]) > 0]
    actual = []
    with fixture_world(args, "ControllerWrench", render=True, pack=args.pack) as world:
        world.commands((
            "/fill 6 177 21 10 182 25 minecraft:air",
            "/setblock 8 176 23 minecraft:smooth_stone",
            "/setblock 9 181 23 minecraft:smooth_stone",
            "/setblock 6 178 23 minecraft:smooth_stone",
            "/tp @s 6.5 179 23.5",
            f"/setblock 8 180 23 {BLOCK}[axis=z]",
            "/data merge block 8 180 23 {ScrollValue:-73}",
            "/setblock 8 180 22 create:creative_motor[facing=south]",
            "/data merge block 8 180 22 {ScrollValue:24}",
            "/setblock 8 180 24 create:shaft[axis=z]",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:wrench",
        ))
        world.call("select", "create:wrench")
        start = world.clock()
        for tick in range(1, 12):
            world.step_to(start + tick)
            actual.append(sample(world, tick))
            if face := FACES.get(tick):
                world.command(f"/tp @s {controller.coords(wrench.APPROACH[face])}")
                world.call("wait", 3)
                if tick == 9:
                    wrench.sneak_click(world, (8.03, 180.67, 23.5))
                else:
                    world.call("interact", *POSITION, face)
                    world.call("wait", 3)
    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    mismatches = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    if mismatches:
        raise RuntimeError(f"{len(mismatches)} Wrench differences. First 8: {mismatches[:8]}")
    print(f"Controller Wrench pose, signed setting, shaft speeds and pickup matched Java for {len(actual)} samples.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/rotation-speed-controller-wrench-horizon.csv")
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
