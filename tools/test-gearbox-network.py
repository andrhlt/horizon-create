#!/usr/bin/env python3
"""Compare a two-Gearbox network through source handoff, loss and reassembly."""

import argparse
import hashlib
import json
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

PIN = "ac0c444d9828da3453ae8cc65338e8de063286fb"
REFERENCE = ROOT / "fixtures/gearbox-network-java.jsonl"
METADATA = ROOT / "fixtures/gearbox-network-java.metadata.json"
PATCH = ROOT / "tools/java-gearbox-network-trace.patch"
POINTS = {
    "a": (8, 104, -10),
    "b": (9, 104, -10),
    "primary": (8, 104, -11),
    "backup": (9, 103, -10),
    "a_west": (7, 104, -10),
    "a_south": (8, 104, -9),
    "b_east": (10, 104, -10),
    "b_up": (9, 105, -10),
    "a_closed": (8, 105, -10),
    "b_closed": (9, 104, -11),
}
DIRECTIONS = ("down", "up", "north", "south", "west", "east")
SHAFT_AXES = {
    "a_west": "x", "a_south": "z", "b_east": "x", "b_up": "y",
    "a_closed": "y", "b_closed": "z",
}


def position(name):
    return " ".join(map(str, POINTS[name]))


def place(name, block):
    return f"/setblock {position(name)} {block}"


def motor(name, facing, rpm):
    return (
        place(name, f"create:creative_motor[facing={facing}]"),
        f"/data merge block {position(name)} {{ScrollValue:{rpm}}}",
    )


ACTIONS = {
    3: (place("primary", "minecraft:air"),),
    9: (place("backup", "minecraft:air"),),
    15: motor("primary", "south", -48),
    21: (place("b", "minecraft:air"),),
    27: (place("b", "create:gearbox[axis=z]"),),
}


def reference():
    metadata = json.loads(METADATA.read_text())
    assert metadata["revision"] == PIN, metadata
    assert metadata["patch_sha256"] == hashlib.sha256(PATCH.read_bytes()).hexdigest(), metadata
    assert metadata["trace_sha256"] == hashlib.sha256(REFERENCE.read_bytes()).hexdigest(), metadata
    rows = [json.loads(line) for line in REFERENCE.read_text().splitlines()]
    assert len(rows) == metadata["records"] == 34
    assert [row["tick"] for row in rows] == list(range(34))
    assert all(row["points"].keys() == POINTS.keys() for row in rows)
    assert all(row["points"][name]["rpm"] == 0
               for row in rows for name in ("a_closed", "b_closed"))
    for tick, a_source, b_source, a_rpm, b_rpm in (
        (3, "north", "west", 32, 32),
        (9, "east", "down", 16, -16),
        (15, "none", "none", 0, 0),
        (21, "north", "west", -48, -48),
        (33, "north", "west", -48, -48),
    ):
        points = rows[tick]["points"]
        assert (points["a"]["source"], points["a"]["rpm"]) == (a_source, a_rpm), rows[tick]
        assert (points["b"]["source"], points["b"]["rpm"]) == (b_source, b_rpm), rows[tick]
    assert rows[27]["points"]["b"]["block"] == "minecraft:air"
    assert rows[27]["points"]["b_up"]["rpm"] == rows[27]["points"]["b_east"]["rpm"] == 0
    return rows


def setup(control):
    control.commands((
        *motor("primary", "south", 32),
        *motor("backup", "up", -16),
        *(place(name, f"create:shaft[axis={axis}]") for name, axis in SHAFT_AXES.items()),
        place("a", "create:gearbox[axis=y]"),
        place("b", "create:gearbox[axis=z]"),
    ))
    start = control.clock()
    for tick in range(1, 9):
        control.step_to(start + tick)


def read_points(control, positions=POINTS):
    coordinates = {name: " ".join(map(str, pos)) for name, pos in positions.items()}
    replies = control.call("script", script="".join(f"block {pos}\n" for pos in coordinates.values()))
    blocks = dict(zip(positions, replies, strict=True))
    points = {name: {"block": state["block"]} for name, state in blocks.items()}
    active = [name for name, state in points.items()
              if state["block"] in ("create:gearbox", "create:shaft", "create:creative_motor")]
    if not active:
        return points
    tags = control.commands(f"/data get block {coordinates[name]}" for name in active)
    for name, tag in zip(active, tags, strict=True):
        rpm = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)", tag)
        assert rpm is not None, (name, tag)
        reading = points[name]
        reading["rpm"] = float(rpm[1])
        if reading["block"] == "create:gearbox":
            state = blocks[name]["state"]
            reading["axis"] = re.search(r"\baxis=([xyz])", state)[1]
            source = re.search(r"\bShaftInputDirection: (-?\d+)", tag)
            assert source is not None, (name, tag)
            index = int(source[1])
            reading["source"] = "none" if index == -1 else DIRECTIONS[index]
    return points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()

    expected = reference()
    output = ROOT / ".local/gearbox-network-horizon.json"
    rows, mismatches = [], []
    try:
        with fixture_world(args, "GearboxNetwork") as control:
            setup(control)
            start = control.clock()
            for reference_row in expected:
                tick = reference_row["tick"]
                if tick:
                    control.step_to(start + tick)
                actual = read_points(control)
                rows.append({"tick": tick, "points": actual})
                for name, want in reference_row["points"].items():
                    if actual[name] != want:
                        mismatches.append({"tick": tick, "point": name, "java": want, "horizon": actual[name]})
                if tick in ACTIONS:
                    control.commands(ACTIONS[tick])
    finally:
        output.write_text(json.dumps({"rows": rows, "mismatches": mismatches}, indent=2) + "\n")
    assert not mismatches, f"{len(mismatches)} mismatches. First: {mismatches[0]}. See {output}."
    print(f"Matched {len(rows)} ticks across {len(POINTS)} points in a two-Gearbox network.")


if __name__ == "__main__":
    main()
