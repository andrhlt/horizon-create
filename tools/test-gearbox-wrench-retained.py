#!/usr/bin/env python3
"""Verify powered gearbox Wrench use with the source face kept open."""

import argparse
import hashlib
from importlib import import_module
import json
from pathlib import Path

from fixture_world import ROOT, fixture_world

network = import_module("test-gearbox-network")
wrench = import_module("test-gearbox-wrench")
PATCH = ROOT / "tools/java-gearbox-wrench-retained-trace.patch"
REFERENCE = ROOT / "fixtures/gearbox-wrench-retained-java.jsonl"
METADATA = ROOT / "fixtures/gearbox-wrench-retained-java.metadata.json"
POSITION = wrench.POSITION
POSITIONS = {
    "down": (8, 179, 23),
    "up": (8, 181, 23),
    "north": (8, 180, 22),
    "south": (8, 180, 24),
    "west": (7, 180, 23),
    "east": (9, 180, 23),
    "gearbox": POSITION,
}
PORT_AXES = {"down": "y", "up": "y", "north": "z", "south": "z", "west": "x", "east": "x"}
MOTORS = {"x": ("down", "up", -32), "z": ("east", "west", -24)}
CLICKS = {"x": {0: "west", 2: "up"}, "z": {2: "west"}}
AIMS = {
    "west": ((6.5, 179, 23.875), (8.01, 180.875, 23.875)),
    "up": ((9.1, 182, 24.1), (8.875, 180.99, 23.875)),
}


def reference():
    meta = json.loads(METADATA.read_text())
    assert meta["revision"] == network.PIN, meta
    for key, path in (("patch_sha256", PATCH), ("trace_sha256", REFERENCE)):
        assert meta[key] == hashlib.sha256(path.read_bytes()).hexdigest(), meta
    cases = {axis: [] for axis in MOTORS}
    for line in REFERENCE.read_text().splitlines():
        row = json.loads(line)
        assert row["points"].keys() == POSITIONS.keys(), row
        cases[row["case"]].append(row)
    for case, rows in cases.items():
        check_order = []
        for tick in range(6):
            check_order.append((tick, "end_tick"))
            if tick in CLICKS[case]:
                check_order.append((tick, "after_use"))
        assert [(row["tick"], row["phase"]) for row in rows] == check_order, case
        points = {(row["tick"], row["phase"]): row["points"] for row in rows}
        start = points[0, "end_tick"]["gearbox"]
        immediately = points[2, "after_use"]
        changed = {"x": "z", "z": "y"}[case]
        expected_rpm = {"x": -32, "z": 24}[case]
        assert (start["axis"], start["source"], start["rpm"]) == (case, MOTORS[case][0], expected_rpm)
        assert (immediately["gearbox"]["axis"], immediately["gearbox"]["source"]) == (changed, "none")
        assert all(value["rpm"] == 0 for value in immediately.values() if value["block"] != "create:creative_motor")
        assert points[3, "end_tick"]["gearbox"] == (start | {"axis": changed})
        if case == "x":
            assert points[0, "end_tick"] == points[0, "after_use"] == points[1, "end_tick"]
    return cases


def setup(control, axis):
    input_side, facing, setting = MOTORS[axis]
    motor = wrench.xyz(POSITIONS[input_side])
    control.commands((
        "/setblock 6 178 23 minecraft:smooth_stone",
        "/setblock 9 181 24 minecraft:smooth_stone",
        "/gamemode survival",
        f"/setblock {motor} create:creative_motor[facing={facing}]",
        f"/data merge block {motor} {{ScrollValue:{setting}}}",
        *(f"/setblock {wrench.xyz(POSITIONS[face])} create:shaft[axis={shaft_axis}]"
          for face, shaft_axis in PORT_AXES.items() if face != input_side),
        f"/setblock {wrench.xyz(POSITION)} create:gearbox[axis={axis}]",
    ))
    wrench.equip(control)
    start = control.clock()
    for tick in range(1, 9):
        control.step_to(start + tick)


def click(control, face, hits):
    feet, aim = AIMS[face]
    control.command(f"/tp @s {wrench.xyz(feet)}")
    control.call("wait", 2)
    control.call("look-at", *aim)
    observed = control.call("looking-at")
    hits.append({"face": face, "observed": observed})
    hit = observed.get("block") or {}
    assert observed["kind"] == "block" and (hit.get("pos"), hit.get("face")) == (list(POSITION), face), observed
    control.call("mouse", "right", "click")
    control.call("wait", 3)


def replay(args, case, rows, hits):
    with fixture_world(args, f"GearboxWrenchRetained{case.upper()}") as control:
        setup(control, case)
        start = control.clock()
        for tick in range(6):
            if tick:
                control.step_to(start + tick)
            rows.append({"case": case, "tick": tick, "phase": "end_tick",
                         "points": network.read_points(control, POSITIONS)})
            if face := CLICKS[case].get(tick):
                click(control, face, hits)
                assert control.clock() == start + tick, "World tick advanced during Wrench use"
                rows.append({"case": case, "tick": tick, "phase": "after_use",
                             "points": network.read_points(control, POSITIONS)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()

    expected = reference()
    observed, hits = [], []
    output = ROOT / ".local/gearbox-wrench-retained-horizon.json"
    try:
        for case in MOTORS:
            replay(args, case, observed, hits)
    finally:
        output.write_text(json.dumps({"rows": observed, "hits": hits}, indent=2) + "\n")
    differences = [(want, got)
                   for want, got in zip((row for rows in expected.values() for row in rows), observed, strict=True)
                   if want != got]
    assert not differences, f"{len(differences)} mismatches. First: {differences[0]}. See {output}."
    print(f"Matched {len(observed)} powered Wrench samples at all seven points, including the same-axis no-op.")


if __name__ == "__main__":
    main()
