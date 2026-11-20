#!/usr/bin/env python3
"""Compare an actual Gearbox save and reopen with two pinned Java server runs."""

import argparse
import hashlib
from importlib import import_module
import json
from pathlib import Path

from fixture_world import ROOT, fixture_world

network = import_module("test-gearbox-network")
PATCH = ROOT / "tools/java-gearbox-reopen-trace.patch"
REFERENCE = ROOT / "fixtures/gearbox-reopen-java.json"
METADATA = ROOT / "fixtures/gearbox-reopen-java.metadata.json"
WORLD = "GearboxReopen"
POSITIONS = {
    "powered": (8, 104, 8),
    "powered_north": (8, 104, 7),
    "powered_up": (8, 105, 8),
    "below_motor": (8, 103, 8),
    "south_motor": (8, 104, 9),
    "stopped": (13, 104, 8),
    "stopped_south": (13, 104, 9),
    "stopped_east": (14, 104, 8),
    "blocked_motor": (13, 104, 7),
}


def reference():
    meta = json.loads(METADATA.read_text())
    assert meta["revision"] == network.PIN, meta
    for key, path in (("patch_sha256", PATCH), ("trace_sha256", REFERENCE)):
        assert meta[key] == hashlib.sha256(path.read_bytes()).hexdigest(), meta
    records = json.loads(REFERENCE.read_text())
    assert [row["phase"] for row in records] == [
        "before_save", "after_load", "settled", "source_removed", "source_replaced",
    ]
    assert records[0]["points"] == records[1]["points"] == records[2]["points"]
    assert [(row["points"]["powered"]["source"], row["points"]["powered"]["rpm"])
            for row in records] == [("down", -32), ("down", -32), ("down", -32), ("none", 0), ("south", 24)]
    assert all(
        (row["points"]["stopped"]["axis"], row["points"]["stopped"]["rpm"], row["points"]["blocked_motor"]["rpm"])
        == ("z", 0, 32) for row in records
    )
    return records


def step(world, count):
    start = world.clock()
    for tick in range(1, count + 1):
        world.step_to(start + tick)


def capture(world, rows, phase):
    rows.append({"phase": phase, "points": network.read_points(world, POSITIONS)})


def replay(world, rows):
    world.commands((
        "/setblock 8 103 8 create:creative_motor[facing=up]",
        "/data merge block 8 103 8 {ScrollValue:-32}",
        "/setblock 8 104 7 create:shaft[axis=z]",
        "/setblock 8 105 8 create:shaft[axis=y]",
        "/setblock 8 104 8 create:gearbox[axis=x]",
        "/setblock 13 104 7 create:creative_motor[facing=south]",
        "/data merge block 13 104 7 {ScrollValue:32}",
        "/setblock 13 104 9 create:shaft[axis=z]",
        "/setblock 14 104 8 create:shaft[axis=x]",
        "/setblock 13 104 8 create:gearbox[axis=z]",
    ))
    step(world, 11)
    capture(world, rows, "before_save")
    saved_tick = world.clock()
    world.stop()
    save = world.socket.parent / f"game/saves/{WORLD}/level.dat"
    assert save.is_file() and save.stat().st_size > 0, save
    world.open()
    reopened_tick = world.clock()
    assert reopened_tick >= saved_tick, (saved_tick, reopened_tick)
    capture(world, rows, "after_load")
    step(world, 7)
    capture(world, rows, "settled")
    world.command("/setblock 8 103 8 minecraft:air")
    step(world, 1)
    capture(world, rows, "source_removed")
    world.commands((
        "/setblock 8 104 9 create:creative_motor[facing=north]",
        "/data merge block 8 104 9 {ScrollValue:-24}",
    ))
    step(world, 1)
    capture(world, rows, "source_replaced")
    return reopened_tick - saved_tick


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()

    expected = reference()
    observed = []
    elapsed = None
    output = ROOT / ".local/gearbox-reopen-horizon.json"
    try:
        with fixture_world(args, WORLD) as world:
            elapsed = replay(world, observed)
    finally:
        output.write_text(json.dumps({"startup_ticks": elapsed, "rows": observed}, indent=2) + "\n")
    differences = [
        (want["phase"], point, reading, got["points"][point])
        for want, got in zip(expected, observed, strict=True)
        for point, reading in want["points"].items()
        if reading != got["points"][point]
    ]
    assert not differences, f"{len(differences)} mismatches. First: {differences[0]}. See {output}."
    print(f"Matched all {len(expected)} Java save/reopen phases at {len(POSITIONS)} points ({elapsed} startup world ticks).")


if __name__ == "__main__":
    main()
