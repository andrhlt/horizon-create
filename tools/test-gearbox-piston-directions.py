#!/usr/bin/env python3
"""Compare a west push and an upward glued Gearbox payload with Java."""

import argparse
import hashlib
from importlib import import_module
import json
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

piston = import_module("test-mechanical-piston-sticker")
PATCH = ROOT / "tools/java-gearbox-piston-directions-trace.patch"
REFERENCE = ROOT / "fixtures/gearbox-piston-directions-java.jsonl"
METADATA = ROOT / "fixtures/gearbox-piston-directions-java.metadata.json"
PIN = "ac0c444d9828da3453ae8cc65338e8de063286fb"
BASE = (8, 104, 10)
CASES = {
    "west": ((-1, 0, 0), (8, 104, 9), "south", 64, "y"),
    "up": ((0, 1, 0), (7, 104, 10), "east", -64, "x"),
}


def pos(case, distance, east=0):
    x, y, z = [coord + distance * step for coord, step in zip(BASE, CASES[case][0], strict=True)]
    return (x + east, y, z)


def reference():
    meta = json.loads(METADATA.read_text())
    assert meta["revision"] == PIN, meta
    for key, path in (("patch_sha256", PATCH), ("trace_sha256", REFERENCE)):
        assert meta[key] == hashlib.sha256(path.read_bytes()).hexdigest(), meta
    scenarios = {case: [] for case in CASES}
    for entry in REFERENCE.read_text().splitlines():
        sample = json.loads(entry)
        scenarios[sample["case"]].append(sample)
    for case, rows in scenarios.items():
        assert [row["tick"] for row in rows] == list(range(24)), case
        box = f"create:gearbox[axis={CASES[case][4]}]"
        assert any(row["offset"] > 0 and box in row["payload"] for row in rows[:10]), case
        assert rows[10]["state"] == "extended" and rows[10]["offset"] == 1, (case, rows[10])
        assert rows[-1]["state"] == "retracted" and rows[-1]["offset"] == 0, (case, rows[-1])
        if case == "up":
            assert rows[10]["side"] == ["minecraft:air", box] and rows[-1]["side"] == [box, "minecraft:air"]
            assert rows[10]["line"][3] == rows[-1]["line"][2] == "minecraft:stone"
            assert any(box in row["payload"] and "minecraft:stone" in row["payload"] for row in rows[11:]), case
        else:
            assert rows[10]["line"][3] == rows[-1]["line"][3] == box
            assert all(box not in row["payload"] for row in rows[11:]), case
    return scenarios


def setup(control, case):
    _, drive, facing, rpm, axis = CASES[case]
    glued = case == "up"
    start = piston.xyz(pos(case, 1))
    first = str(glued).lower()
    payload = f"create:gearbox[axis={axis}]"
    commands = [
        f"/setblock {piston.xyz(BASE)} create:sticky_mechanical_piston[facing={case},axis_along_first={first}]",
        f"/data merge block {piston.xyz(BASE)} {{ScrollValue:0}}",
        f"/setblock {piston.xyz(pos(case, -1))} create:piston_extension_pole[facing={case}]",
        f"/setblock {start} {'minecraft:stone' if glued else payload}",
    ]
    if glued:
        commands.extend((
            f"/setblock {piston.xyz(pos(case, 1, east=1))} {payload}",
            f"/summon minecraft:marker {start} {{CreateSuperGlue:1b,From:[0d,0d,0d],To:[2d,1d,1d]}}",
        ))
    control.commands((
        *commands,
        f"/setblock {piston.xyz(drive)} create:creative_motor[facing={facing}]",
        f"/data merge block {piston.xyz(drive)} {{ScrollValue:{rpm}}}",
    ))
    for _ in range(2):
        control.step_to(control.clock() + 1)


def cells(control, coords):
    replies = control.call("script", script="".join(f"block {piston.xyz(at)}\n" for at in coords))
    return [reply["state"] if reply["block"] == "create:gearbox" else reply["block"] for reply in replies]


def read_state(control, case):
    base = piston.xyz(BASE)
    data = control.command(f"/data get block {base}")
    state = re.search(r"\bstate=(\w+)", control.call("block", *BASE)["state"])[1]
    payload = []
    if state == "moving":
        blocks = control.command(f"/data get block {base} Blocks")
        payload = piston.ids_from_payload(blocks)
        if "create:gearbox" in payload:
            axis = re.search(r'\baxis:\s*"([xyz])"', blocks)
            assert axis is not None, blocks
            payload[payload.index("create:gearbox")] = f"create:gearbox[axis={axis[1]}]"
    return {
        "state": state,
        "offset": piston.field(data, "Offset"),
        "rpm": piston.field(data, "Speed"),
        "line": cells(control, [pos(case, distance) for distance in range(-1, 4)]),
        "side": cells(control, [pos(case, distance, east=1) for distance in (1, 2)]) if case == "up" else [],
        "payload": sorted(payload),
    }


def replay(args, case, expected, rows):
    with fixture_world(args, f"GearboxPistonDirection{case.capitalize()}") as control:
        setup(control, case)
        _, drive, _, rpm, _ = CASES[case]
        start = control.clock()
        for want in expected:
            tick = want["tick"]
            if tick:
                control.step_to(start + tick)
            if tick == 10:
                control.command(f"/data merge block {piston.xyz(drive)} {{ScrollValue:{-rpm}}}")
            rows.append({"case": case, "tick": tick, **read_state(control, case)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()

    expected = reference()
    observed = []
    artifact = ROOT / ".local/gearbox-piston-directions-horizon.json"
    try:
        for case, rows in expected.items():
            replay(args, case, rows, observed)
    finally:
        artifact.write_text(json.dumps(observed, indent=2) + "\n")
    differences = [(want, got)
                   for want, got in zip((row for rows in expected.values() for row in rows), observed, strict=True)
                   if want != got]
    assert not differences, f"{len(differences)} mismatches. First: {differences[0]}. See {artifact}."
    print(f"Matched {len(observed)} Java piston samples across the west push and upward glued payload.")


if __name__ == "__main__":
    main()
