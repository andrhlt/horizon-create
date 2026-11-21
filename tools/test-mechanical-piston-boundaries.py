#!/usr/bin/env python3
"""Source-derived piston facing, pole-length, speed and Horizon reopen checks.

These assertions exercise the pinned MechanicalPistonBlockEntity and
LinearActuatorBlockEntity rules; they are not an exact Java reload trace.
"""

import argparse
from importlib import import_module
import json
from pathlib import Path
import re

from fixture_world import ROOT, fixture_world

piston = import_module("test-mechanical-piston-sticker")
# facing, normal, drive offset, drive facing, axis_along_first, extension RPM
FACES = (
    ("east", (1, 0, 0), (0, 0, -1), "south", False, -64),
    ("west", (-1, 0, 0), (0, 0, -1), "south", False, 64),
    ("up", (0, 1, 0), (-1, 0, 0), "east", True, -64),
    ("down", (0, -1, 0), (-1, 0, 0), "east", True, 64),
    ("north", (0, 0, -1), (-1, 0, 0), "east", True, -64),
    ("south", (0, 0, 1), (-1, 0, 0), "east", True, 64),
)
CASES = [(face, 1) for face in FACES] + [(FACES[0], 4)]


def add(at, normal, distance=1):
    return tuple(a + d * distance for a, d in zip(at, normal, strict=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("ctl", "client", "resources"):
        parser.add_argument(key, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    args = parser.parse_args()
    rigs = []
    for index, (face, length) in enumerate(CASES):
        direction, normal, drive_offset, drive_face, first, rpm = face
        base = (8 + 20 * (index % 3), 120, 10 + 20 * (index // 3))
        rigs.append(dict(name=f"{direction}-{length}", base=base, normal=normal,
                         motor=add(base, drive_offset), direction=direction,
                         drive_face=drive_face, first=first, rpm=rpm, length=length))
    phases = []
    artifact = ROOT / ".local/mechanical-piston/boundaries-horizon.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    with fixture_world(args, "PistonBoundaries", pack=args.pack) as control:
        def step(count):
            for _ in range(count):
                control.step_to(control.clock() + 1)

        def speed(multiplier):
            control.commands(f'/data merge block {piston.xyz(r["motor"])} {{ScrollValue:{int(r["rpm"] * multiplier)}}}' for r in rigs)

        def snapshot(label):
            rows = []
            for r in rigs:
                data = control.command(f'/data get block {piston.xyz(r["base"])}')
                block = control.call("block", *r["base"])
                rows.append(dict(name=r["name"], offset=piston.field(data, "Offset"),
                                 speed=piston.field(data, "Speed"), mode=piston.field(data, "ScrollValue"),
                                 state=re.search(r"\bstate=(\w+)", block["state"])[1],
                                 payload=piston.ids_from_payload(data),
                                 cells=[control.call("block", *add(r["base"], r["normal"], d))["block"]
                                        for d in range(-r["length"], r["length"] + 3)]))
            phases.append(dict(phase=label, rows=rows))
            artifact.write_text(json.dumps(phases, indent=2) + "\n")
            return rows

        for r in rigs:
            base, normal = r["base"], r["normal"]
            control.commands((
                f'/setblock {piston.xyz(base)} create:sticky_mechanical_piston[facing={r["direction"]},axis_along_first={str(r["first"]).lower()}]',
                f'/data merge block {piston.xyz(base)} {{ScrollValue:2}}',
                *(f'/setblock {piston.xyz(add(base, normal, -d))} create:piston_extension_pole[facing={r["direction"]}]'
                  for d in range(1, r["length"] + 1)),
                f'/setblock {piston.xyz(add(base, normal))} minecraft:stone',
                f'/setblock {piston.xyz(r["motor"])} create:creative_motor[facing={r["drive_face"]}]',
                f'/data merge block {piston.xyz(r["motor"])} {{ScrollValue:{r["rpm"]}}}',
            ))
        step(38)
        extended = snapshot("extended")
        assert all(row["state"] == "moving" and row["offset"] == rig["length"]
                   and "minecraft:stone" in row["payload"] for row, rig in zip(extended, rigs, strict=True)), extended
        speed(-1)
        step(4)
        # Slow the active setup so the four-pole payload stays in flight during
        # the server's startup interval before the control tool freezes it.
        speed(-1 / 16)
        step(2)
        active = snapshot("active")
        assert all(0 < row["offset"] < rig["length"] for row, rig in zip(active, rigs, strict=True)), active
        # Launch resumes server ticks before FixtureWorld.open can freeze them.
        # Compare retained settings/cargo and bounded continuation, not an exact
        # paused offset or Java-equivalent reload timing.
        saved_clock = control.clock()
        control.restart()
        reopened = snapshot("active-reopened")
        phases[-1]["elapsed_world_ticks"] = control.clock() - saved_clock
        for before, after in zip(active, reopened, strict=True):
            assert {k: v for k, v in before.items() if k != "offset"} == {k: v for k, v in after.items() if k != "offset"}, (before, after)
            assert 0 <= after["offset"] <= before["offset"], (before, after)
        assert reopened[-1]["offset"] > 0, "four-pole fixture completed before the active reload observation"
        step(1)
        resumed = snapshot("active-resumed")
        assert all(after["offset"] == max(0, before["offset"] - .0078125)
                   for before, after in zip(reopened, resumed, strict=True)), resumed
        speed(0)
        step(3)
        stopped = snapshot("zero")
        assert all(row["offset"] == old["offset"] and row["state"] == "moving" and row["speed"] == 0
                   for row, old in zip(stopped, resumed, strict=True)), stopped
        speed(-2)
        step(2)
        faster = snapshot("faster-return")
        assert all(old["offset"] - row["offset"] == min(old["offset"], .25)
                   for row, old in zip(faster, stopped, strict=True)), faster
        step(18)
        returned = snapshot("returned-mounted")
        assert all(row["offset"] == 0 for row in returned), returned
        control.commands(f'/data merge block {piston.xyz(r["base"])} {{ScrollValue:0}}' for r in rigs)
        step(1)
        speed(0)
        step(1)
        idle = snapshot("idle")
        assert all(row["state"] == "retracted" and row["speed"] == 0 and not row["payload"]
                   and row["cells"][rig["length"] + 1] == "minecraft:stone"
                   for row, rig in zip(idle, rigs, strict=True)), idle
        control.restart()
        assert snapshot("idle-reopened") == idle, "idle state changed across Horizon reopen"
    print("Passed seven source-derived rigs: six facings, one/four poles, reversal, zero, doubled speed, active/idle Horizon reopen.")


if __name__ == "__main__":
    main()
