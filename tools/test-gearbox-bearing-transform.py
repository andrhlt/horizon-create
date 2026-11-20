#!/usr/bin/env python3
"""Replay the quarter-turn disassembly of two glued Gearboxes."""

import argparse
import hashlib
from importlib import import_module
import json
from pathlib import Path

from fixture_world import ROOT, fixture_world

network = import_module("test-gearbox-network")
piston = import_module("test-mechanical-piston-sticker")
PATCH = ROOT / "tools/java-gearbox-bearing-transform-trace.patch"
REFERENCE = ROOT / "fixtures/gearbox-bearing-transform-java.json"
METADATA = ROOT / "fixtures/gearbox-bearing-transform-java.metadata.json"
BEARING = "8 104 10"
DRIVE = "8 103 10"
POINTS = {
    "center": (8, 105, 10),
    "east": (9, 105, 10),
    "north": (8, 105, 9),
    "south": (8, 105, 11),
}


def reference():
    meta = json.loads(METADATA.read_text())
    assert meta["revision"] == network.PIN, meta
    for key, path in (("patch_sha256", PATCH), ("trace_sha256", REFERENCE)):
        assert meta[key] == hashlib.sha256(path.read_bytes()).hexdigest(), meta
    rows = json.loads(REFERENCE.read_text())
    assert [row["phase"] for row in rows] == ["before", "quarter_turn", "restored", "settled"]
    before, turning, restored, settled = rows
    assert before["points"]["center"]["axis"] == "x" and before["points"]["center"]["rpm"] != 0
    assert before["points"]["east"]["axis"] == "z"
    assert turning["running"] and abs(turning["angle"]) == 90
    assert all(point["block"] == "minecraft:air" for point in turning["points"].values())
    assert not restored["running"] and not settled["running"]
    assert restored["points"]["center"]["axis"] == "z" and settled["points"]["center"]["source"] == "up"
    assert any(restored["points"][side].get("axis") == "x" for side in ("north", "south"))
    return rows


def state(control, phase):
    data = control.command(f"/data get block {BEARING}")
    return {
        "phase": phase,
        "running": bool(piston.field(data, "Running")),
        "angle": piston.field(data, "Angle"),
        "points": network.read_points(control, POINTS),
    }


def replay(control, observed):
    control.commands((
        f"/setblock {BEARING} create:mechanical_bearing[facing=up]",
        f"/data merge block {BEARING} {{ScrollValue:0}}",
        "/setblock 8 105 10 create:gearbox[axis=x]",
        "/setblock 9 105 10 create:gearbox[axis=z]",
        "/summon minecraft:marker 8 105 10 {CreateSuperGlue:1b,From:[0d,0d,0d],To:[2d,1d,1d]}",
        "/setblock 8 106 10 create:creative_motor[facing=down]",
        "/data merge block 8 106 10 {ScrollValue:32}",
        f"/setblock {DRIVE} create:creative_motor[facing=up]",
        f"/data merge block {DRIVE} {{ScrollValue:0}}",
    ))
    for _ in range(8):
        control.step_to(control.clock() + 1)
    observed.append(state(control, "before"))
    control.command(f"/data merge block {DRIVE} {{ScrollValue:60}}")
    for _ in range(20):
        control.step_to(control.clock() + 1)
        sample = state(control, "quarter_turn")
        if sample["running"] and abs(abs(sample["angle"]) - 90) < 0.001:
            observed.append(sample)
            break
    else:
        raise AssertionError(f"Bearing never reached the quarter-turn: {sample}")
    control.command(f"/data merge block {DRIVE} {{ScrollValue:0}}")
    control.step_to(control.clock() + 1)
    observed.append(state(control, "restored"))
    for _ in range(3):
        control.step_to(control.clock() + 1)
    observed.append(state(control, "settled"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()

    expected = reference()
    observed = []
    output = ROOT / ".local/gearbox-bearing-transform-horizon.json"
    try:
        with fixture_world(args, "GearboxBearingTransform") as control:
            replay(control, observed)
    finally:
        output.write_text(json.dumps(observed, indent=2) + "\n")
    differences = [(want, got) for want, got in zip(expected, observed, strict=True) if want != got]
    assert not differences, f"{len(differences)} phases differ. First: {differences[0]}. See {output}."
    print("Matched the Java bearing quarter-turn and both Gearbox axes and kinetic states after disassembly.")


if __name__ == "__main__":
    main()
