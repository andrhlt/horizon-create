#!/usr/bin/env python3
"""Replay pinned Java Gearbox links and equal-speed source joins."""

import argparse
import hashlib
from importlib import import_module
from itertools import groupby
import json
from pathlib import Path

from fixture_world import ROOT, fixture_world

network = import_module("test-gearbox-network")
PATCH = ROOT / "tools/java-gearbox-topology-trace.patch"
REFERENCE = ROOT / "fixtures/gearbox-topology-java.jsonl"
METADATA = ROOT / "fixtures/gearbox-topology-java.metadata.json"
ORIGIN = (8, 104, -10)
SIDES = {
    "down": (0, -1, 0), "up": (0, 1, 0), "north": (0, 0, -1), "south": (0, 0, 1),
    "west": (-1, 0, 0), "east": (1, 0, 0),
}
OPPOSITE = dict(zip(SIDES, ("up", "down", "south", "north", "east", "west"), strict=True))
AXIS = {side: "xyz"[next(index for index, value in enumerate(delta) if value)]
        for side, delta in SIDES.items()}


def reference():
    meta = json.loads(METADATA.read_text())
    assert meta["revision"] == network.PIN, meta
    for key, path in (("patch_sha256", PATCH), ("trace_sha256", REFERENCE)):
        assert meta[key] == hashlib.sha256(path.read_bytes()).hexdigest(), meta
    rows = [json.loads(line) for line in REFERENCE.read_text().splitlines()]
    assert len(rows) == meta["records"] == 15
    groups = [list(samples) for _, samples in groupby(rows, key=lambda row: row["case"])]
    assert len(groups) == meta["cases"] == 11
    assert {group[0]["input"] for group in groups} == set(SIDES)
    for samples in groups:
        first = samples[0]
        phases = ["before_join", "joined_1", "joined_4"] if "backup_dial" in first else ["settled"]
        assert [row["phase"] for row in samples] == phases, first
        assert all(row["points"].keys() == positions(row).keys() for row in samples), first
        for box in ("a", "b"):
            for side, axis in AXIS.items():
                point = first["points"].get(f"{box}_{side}")
                if point and axis == first[f"{box}_axis"]:
                    assert point["block"] == "create:shaft" and point["rpm"] == 0, first
    return groups


def neighbor(pos, side):
    return tuple(value + shift for value, shift in zip(pos, SIDES[side], strict=True))


def positions(case):
    side = case["link"]
    second = neighbor(ORIGIN, side)
    points = {"a": ORIGIN, "b": second}
    for face in SIDES:
        if face != side:
            points[f"a_{face}"] = neighbor(ORIGIN, face)
        if face != OPPOSITE[side]:
            points[f"b_{face}"] = neighbor(second, face)
    return points


def coords(pos):
    return " ".join(map(str, pos))


def motor(pos, side, dial):
    return (
        f"/setblock {coords(pos)} create:creative_motor[facing={OPPOSITE[side]}]",
        f"/data merge block {coords(pos)} {{ScrollValue:{dial}}}",
    )


def setup(control, case, points):
    commands = ["/fill 6 102 -12 10 106 -8 minecraft:air"]
    primary = f'a_{case["input"]}'
    backup = f'b_{case["link"]}'
    for name, pos in points.items():
        if name == primary:
            commands.extend(motor(pos, case["input"], case["dial"]))
        elif name == backup and "backup_dial" in case:
            commands.extend(motor(pos, case["link"], case["backup_dial"]))
        elif name not in ("a", "b"):
            commands.append(f"/setblock {coords(pos)} create:shaft[axis={AXIS[name[2:]]}]")
    commands.append(f'/setblock {coords(points["a"])} create:gearbox[axis={case["a_axis"]}]')
    join = f'/setblock {coords(points["b"])} create:gearbox[axis={case["b_axis"]}]'
    if "backup_dial" not in case:
        commands.append(join)
    control.commands(commands)
    return join


def replay(control, groups, rows, mismatches):
    for samples in groups:
        points = positions(samples[0])
        join = setup(control, samples[0], points)
        start = control.clock()
        for tick in range(1, 7):
            control.step_to(start + tick)
        for want in samples:
            phase = want["phase"]
            if phase == "joined_1":
                control.step_to(start + 7, before=join)
            elif phase == "joined_4":
                for tick in range(8, 11):
                    control.step_to(start + tick)
            actual = network.read_points(control, points)
            rows.append(want | {"points": actual})
            for name, expected in want["points"].items():
                if actual[name] != expected:
                    mismatches.append({"case": want["case"], "phase": phase, "point": name,
                                       "java": expected, "horizon": actual[name]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    groups = reference()
    rows, mismatches = [], []
    output = ROOT / ".local/gearbox-topology-horizon.json"
    try:
        with fixture_world(args, "GearboxTopology") as control:
            replay(control, groups, rows, mismatches)
    finally:
        output.write_text(json.dumps({"rows": rows, "mismatches": mismatches}, indent=2) + "\n")
    assert not mismatches, f"{len(mismatches)} mismatches. First: {mismatches[0]}. See {output}."
    print(f"Matched {len(rows)} samples in {len(groups)} pinned Java Gearbox topology cases.")


if __name__ == "__main__":
    main()
