#!/usr/bin/env python3
"""Replay mixed chain drive placement and neighbor changes on every axis."""

import argparse
import csv
import math
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

AXES = ("x", "y", "z")
CASES = [(shaft, chain) for shaft in AXES for chain in AXES if shaft != chain]
DRIVE = "create:encased_chain_drive"
GEARSHIFT = "create:adjustable_chain_gearshift"
NAMES = {DRIVE: "drive", GEARSHIFT: "gearshift"}
NEGATIVE_FACE = ("west", "down", "north")
PHASES = (
    "single", "pair", "triple", "remove_end", "different_shaft", "incompatible",
    "restore_end", "split", "restore_middle",
)
HEADER = ("shaft_axis", "chain_axis", "phase", "negative", "center", "positive")


def coords(pos):
    return " ".join(map(str, pos))


def offset(pos, axis, amount):
    return tuple(value + amount if axis == index else value for index, value in enumerate(pos))


def remove(control, pos):
    control.command(f"/setblock {coords(pos)} minecraft:air")


def place(control, pos, shaft, chain, block):
    axis = AXES.index(shaft)
    support = offset(pos, axis, 1)
    control.command(f"/setblock {coords(support)} create:shaft[axis={shaft}]")
    center = tuple(value + 0.5 for value in pos)
    if shaft == chain:
        # Approach the incompatible link-facing end from the side.
        sideways = 2 if axis == 0 else 0
        eyes = offset(offset(center, axis, -0.2), sideways, 2)
    else:
        eyes = offset(center, axis, -1.75)
    feet = offset(eyes, 1, -1.62)
    control.command(f"/tp @s {coords(feet)}")
    control.call("wait", 2)
    control.call("select", block)
    control.call("interact", *support, NEGATIVE_FACE[axis])
    state = control.call("block", *pos)["state"]
    if state.split("[", 1)[0] != block:
        raise RuntimeError(f"Expected {block} at {pos} after placement against {support}, got {state}")
    remove(control, support)


def chain_state(state):
    name, _, properties = state.partition("[")
    if name in ("minecraft:air", "minecraft:cave_air"):
        return "air"
    values = dict(value.split("=", 1) for value in properties.removesuffix("]").split(","))
    return ":".join((
        NAMES[name], values["axis"], values["axis_along_first"], values["part"],
        values.get("powered", "-"),
    ))


def replay(control, index, shaft, chain):
    control.command("/fill 5 98 -14 13 108 -6 minecraft:air")
    center = (9, 103, -10)
    axis = AXES.index(chain)
    left, right = offset(center, axis, -1), offset(center, axis, 1)
    end_block, center_block = (DRIVE, GEARSHIFT) if index % 2 == 0 else (GEARSHIFT, DRIVE)
    alternate, = set(AXES) - {shaft, chain}

    def sample(phase):
        states = control.call("script", script="".join(f"block {coords(pos)}\n" for pos in (left, center, right)))
        return (shaft, chain, phase, *(chain_state(result["state"]) for result in states))

    place(control, left, shaft, chain, end_block)
    yield sample("single")
    place(control, center, shaft, chain, center_block)
    yield sample("pair")
    place(control, right, shaft, chain, end_block)
    yield sample("triple")
    remove(control, right)
    yield sample("remove_end")
    place(control, right, alternate, chain, end_block)
    yield sample("different_shaft")
    remove(control, right)
    place(control, right, chain, chain, end_block)
    yield sample("incompatible")
    remove(control, right)
    place(control, right, shaft, chain, end_block)
    yield sample("restore_end")
    remove(control, center)
    control.command("/tick step 1")
    yield sample("split")
    place(control, center, shaft, chain, center_block)
    yield sample("restore_middle")


def verify(args):
    with (ROOT / "fixtures/chain-drive-placement-java.csv").open() as source:
        header, *rows = list(csv.reader(source))
    if tuple(header) != HEADER or [tuple(row[:3]) for row in rows] != [
        (shaft, chain, phase) for shaft, chain in CASES for phase in PHASES
    ]:
        raise RuntimeError("The Java trace must include all nine phases for each of the six axis arrangements.")
    expected = list(map(tuple, rows))
    with fixture_world(
        args,
        "ChainDrivePlacement",
        render=True,
        env={"CREATE_CHAIN_DRIVE_RENDER": "1"},
        pack=args.pack,
    ) as control:
        control.command("/tick unfreeze")
        control.call("script", script=(
            "key space down\nwait 1\nkey space up\nwait 1\n"
            "key space down\nwait 1\nkey space up\n"
        ))
        if not control.call("state")["player"]["flying"]:
            raise RuntimeError("Creative flight is needed to hold the placement positions.")
        control.command("/tick freeze")
        control.commands((
            "/fill 4 97 -15 14 97 -5 minecraft:smooth_stone",
            f"/item replace entity @s hotbar.0 with {DRIVE}",
            f"/item replace entity @s hotbar.1 with {GEARSHIFT}",
        ))
        actual = [row for index, (shaft, chain) in enumerate(CASES) for row in replay(control, index, shaft, chain)]
    log = ROOT / ".local/horizon-chaindriveplacement.log"
    frames = []
    for line in log.read_text(encoding="utf-8").splitlines():
        match = re.search(
            r"CREATE_CHAIN_DRIVE_FRAME (-?\d+) (-?\d+) (-?\d+) (\d+) (\d+) "
            r"([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) (\d+)",
            line,
        )
        if match:
            x, y, z, axis, tick, partial, rpm, phase, angle, vertices = match.groups()
            frames.append((tuple(map(int, (x, y, z))), int(axis), int(tick), *map(float, (partial, rpm, phase, angle)), int(vertices)))
    if not frames or {frame[1] for frame in frames} != {0, 1, 2}:
        raise RuntimeError("Expected rendered chain-drive shaft geometry on all three axes.")
    for pos, axis, tick, partial, rpm, phase, angle, vertices in frames:
        expected_angle = math.fmod((tick + partial) * rpm * 3.0 / 10.0 + phase, 360.0)
        expected_phase = 22.5 if sum(pos[index] for index in range(3) if index != axis) % 2 == 0 else 0.0
        if vertices <= 0 or phase != expected_phase or abs(angle - expected_angle) > 2e-5:
            raise RuntimeError(f"Unexpected chain-drive frame transform: {pos}, axis={axis}, tick={tick}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as target:
        writer = csv.writer(target)
        writer.writerow(HEADER)
        writer.writerows(actual)
    differences = [(want, got) for want, got in zip(expected, actual, strict=True) if want != got]
    if differences:
        raise RuntimeError(f"{len(differences)} chain state differences (Java, Horizon): {differences[:8]}")
    print(
        f"Chain drive placement matched Java across {len(CASES)} axis arrangements and "
        f"{len(actual)} snapshots; shaft geometry rendered on three axes in {len(frames)} frames."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/chain-drive-placement-horizon.csv")
    verify(parser.parse_args())


if __name__ == "__main__":
    main()
