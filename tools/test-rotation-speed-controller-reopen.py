#!/usr/bin/env python3
"""Compare controller target and transmission across a cold world reopen."""

import argparse
import csv
from importlib import import_module
from pathlib import Path

from fixture_world import ROOT, fixture_world

controller = import_module("test-rotation-speed-controller")
coords = controller.coords
tag = controller.tag

CASES = ((6, True, -73), (14, False, 83), (22, True, 0), (30, False, 0))


def layout(x, cog_driven):
    base = (x, 101, -10)
    cog = (x, 102, -10)
    motor = (x - 1, 102, -10) if cog_driven else (x, 101, -11)
    return (base, cog, (x, 101, -9), (x + 1, 102, -10), motor)


def set_up(world):
    world.commands((
        "/fill 3 100 -13 33 104 -7 minecraft:air",
        "/fill 3 100 -13 33 100 -7 minecraft:smooth_stone",
        "/tp @s 5.5 101 -9.5",
    ))
    for x, cog_driven, setting in CASES:
        base, cog, shaft, cog_shaft, motor = map(coords, layout(x, cog_driven))
        world.commands((
            f"/setblock {base} create:rotation_speed_controller[axis=z]",
            f"/data merge block {base} {{ScrollValue:{setting}}}",
            f"/setblock {cog} create:large_cogwheel[axis=x]",
            f"/setblock {shaft} create:shaft[axis=z]",
            f"/setblock {cog_shaft} create:shaft[axis=x]",
            f"/setblock {motor} create:creative_motor[facing={'east' if cog_driven else 'south'}]",
            f"/data merge block {motor} {{ScrollValue:24}}",
        ))


def sample(world, tick):
    rows = []
    for index, (x, cog_driven, _) in enumerate(CASES):
        tags = world.commands(f"/data get block {coords(pos)}" for pos in layout(x, cog_driven))
        setting = tag(tags[0], "ScrollValue", int)
        speeds = [tag(nbt, "Speed", float) for nbt in tags]
        rows.append((*map(str, (tick, index, setting)), *(f"{rpm:.4f}" for rpm in speeds)))
    return rows


def verify(args):
    with (ROOT / "fixtures/rotation-speed-controller-reopen-java.csv").open() as stream:
        header, *rows = list(csv.reader(stream))
    expected = list(map(tuple, rows))
    with fixture_world(args, "ControllerReopen", pack=args.pack) as world:
        set_up(world)
        start = world.clock()
        for tick in range(1, 7):
            world.step_to(start + tick)
        saved_clock = world.clock()
        actual = sample(world, -1)
        world.call("save")
        world.env["HORIZON_STILL"] = "1"
        world.restart()
        if world.clock() != saved_clock:
            raise RuntimeError("The reopened world advanced before the initial sample.")
        actual.extend(sample(world, 0))
        for tick in range(1, 7):
            world.step_to(saved_clock + tick)
            actual.extend(sample(world, tick))
    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    mismatch = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    if mismatch:
        raise RuntimeError(f"{len(mismatch)} reopen differences. First 8: {mismatch[:8]}")
    print(f"Signed and zero targets matched Java across {len(actual)} saved and reopened samples.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/rotation-speed-controller-reopen-horizon.csv")
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
