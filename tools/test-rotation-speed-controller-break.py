#!/usr/bin/env python3
"""Check which cog breaks when a controller setting exceeds the mesh RPM limit."""

import argparse
import csv
import runpy
from pathlib import Path

from fixture_world import ROOT, fixture_world

SETTINGS_FIXTURE = runpy.run_path(str(Path(__file__).with_name("test-rotation-speed-controller.py")))
configure = SETTINGS_FIXTURE["configure"]
tag = SETTINGS_FIXTURE["tag"]
coords = SETTINGS_FIXTURE["coords"]

BLOCKS = ("rotation_speed_controller", "large_cogwheel", "cogwheel", "creative_motor")
RIGS = [
    ((x, 101, -10), (x, 102, -10), (x + 1, 103, -10),
     (x, 102, -9) if case == 3 else (x - 1, 101, -10))
    for case, x in enumerate((10, 16, 22, 28))
]
SETTINGS = {4: 128, 8: 129, 12: 48}


def sample(control, tick, case):
    rig = RIGS[case]
    blocks = [control.call("block", *pos)["state"].split("[", 1)[0] for pos in rig]
    present = [int(block == f"create:{name}") for block, name in zip(blocks, BLOCKS, strict=True)]
    data = iter(control.commands(f"/data get block {coords(pos)}" for pos, exists in zip(rig, present) if exists))
    tags = [next(data) if exists else None for exists in present]
    setting = tag(tags[0], "ScrollValue", int) if tags[0] is not None else 0
    speeds = [tag(nbt, "Speed", float) if nbt is not None else 0.0 for nbt in tags]
    return (*map(str, (tick, case, *present, setting)), *(f"{rpm:.4f}" for rpm in speeds))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/rotation-speed-controller-break-horizon.csv")
    args = parser.parse_args()
    with (ROOT / "fixtures/rotation-speed-controller-break-java.csv").open() as stream:
        header, *rows = list(csv.reader(stream))
    expected = [tuple(row) for row in rows if int(row[0]) > 0]
    actual = []
    with fixture_world(args, "rotation-speed-controller-break", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 6 100 -13 31 104 -8 minecraft:air",
            "/fill 6 100 -13 31 100 -8 minecraft:smooth_stone",
            "/tp @s 6 101 -10",
            "/gamemode survival",
        ))
        for case, (controller, large, small, motor) in enumerate(RIGS):
            control.commands((
                f"/setblock {coords(controller)} create:rotation_speed_controller[axis=x]",
                f"/setblock {coords(large)} create:large_cogwheel[axis=z]",
                f"/setblock {coords(small)} create:cogwheel[axis=z]",
            ))
            if case != 2:
                facing, rpm = ("north", -24) if case == 3 else ("east", 24)
                control.commands((
                    f"/setblock {coords(motor)} create:creative_motor[facing={facing}]",
                    f"/data merge block {coords(motor)} {{ScrollValue:{rpm}}}",
                ))
        start = control.clock()
        for tick in range(1, 19):
            control.step_to(start + tick)
            actual.extend(sample(control, tick, case) for case in range(len(RIGS)))
            if tick in SETTINGS:
                for case, rig in enumerate(RIGS):
                    configure(control, rig[0], 1 - case % 2, SETTINGS[tick], axis="x")
            if tick == 14:
                control.commands(f"/setblock {coords(rig[1])} create:large_cogwheel[axis=z]" for rig in RIGS)

    with args.output.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(actual)
    differences = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    if differences:
        raise RuntimeError(f"{len(differences)} break-order differences. First 8: {differences[:8]}")
    print(f"Both signed RPM limit transitions and cog replacement matched Java for {len(actual)} samples.")


if __name__ == "__main__":
    main()
