#!/usr/bin/env python3
"""Compare submitted Girder wrench highlight bounds and capture actual frames."""
import argparse
import csv
import importlib.util
from pathlib import Path

from fixture_world import ROOT, fixture_world

path = ROOT / "tools/test-metal-girder-wrench.py"
spec = importlib.util.spec_from_file_location(path.stem, path)
wrench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrench)
NONE = ("none", False, *(0.0 for _ in range(8)))


def values(row):
    direction, paired, *numbers = row
    return direction, paired == "true", *(float(number) for number in numbers)


def sample(args, index, *, sneaking=False, stowed=False):
    scenario = (0, 0, 1, 2)[index]
    name = f"GirderWrenchOutline{index}{'Sneak' if sneaking else 'Stowed' if stowed else ''}"
    env = {"CREATE_GIRDER_WRENCH_OUTLINE": "1"}
    with fixture_world(args, name, render=True, pack=args.pack, env=env) as control:
        wrench.setup(control, scenario)
        if stowed:
            control.command("/item replace entity @s hotbar.0 with minecraft:air")
        x, y, z = wrench.BASE
        control.commands(("/time set noon", f"/tp @s {x + 0.5:.3f} {y}.000 {z - 2.5:.3f}"))
        control.call("wait", 3)
        if sneaking:
            control.call("key", "shift", "down")
            control.call("wait", 3)
        aim_y = y + (0.17 if index == 1 else 0.80)
        aim_z = z + (0.001 if scenario == 2 else 0.251)
        control.call("look-at", x + 0.5, aim_y, aim_z)
        control.call("wait", 3)
        hit = control.call("looking-at").get("block")
        if not hit or hit["pos"] != [x, y, z]:
            raise RuntimeError(f"Case {name} failed to put the crosshair on the original beam: {hit}")
        if args.frames is not None:
            args.frames.mkdir(parents=True, exist_ok=True)
            control.call("screenshot", args.frames / f"{name}.png")
    trace = ROOT / f".local/horizon-{name.lower()}.log"
    with trace.open() as stream:
        frames = [line.split(" ", 1)[1].strip().split(",") for line in stream
                  if line.startswith("CREATE_GIRDER_WRENCH_OUTLINE ")]
    return values(frames[-1]) if frames else NONE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--frames", type=Path)
    args = parser.parse_args()
    with (ROOT / "fixtures/metal-girder-wrench-preview-java.csv").open() as stream:
        _, *rows = list(csv.reader(stream))
    results = [(int(index), values(expected), sample(args, int(index))) for index, *expected in rows]
    results.append(("sneak", NONE, sample(args, 0, sneaking=True)))
    results.append(("stowed", NONE, sample(args, 0, stowed=True)))
    differing = [(index, expected, got) for index, expected, got in results if got != expected]
    if differing:
        raise RuntimeError(f"Girder wrench outline differences: {differing}")
    print("Girder wrench outline matches three Java boxes, cross rejection and both hidden inputs.")


if __name__ == "__main__":
    main()
