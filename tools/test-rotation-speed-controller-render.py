#!/usr/bin/env python3
"""Compare actual offscreen controller shaft and bracket submissions with Java."""
import argparse
import csv
from math import isclose
from pathlib import Path

from controller_render_fixture import CAMERA, FIELDS, PART_FIELDS, RIGS, STAGES, frames, setup, stage_commands, stage_state
from fixture_world import ROOT, fixture_world


def replay(args):
    with fixture_world(args, "ControllerRender", render=True, pack=args.pack,
                       env={"CREATE_CONTROLLER_RENDER": "1"}) as world:
        world.commands(("/time set midnight", "/gamemode spectator", *("/" + cmd for cmd in setup()),
                        f"/tp @s {CAMERA}"))
        world.call("wait-ready")
        for _ in range(4):
            world.step_to(world.clock() + 1)
        world.command("/tick unfreeze")
        log = world.socket.parent / "ctl.log"
        actual = []
        for stage in STAGES:
            offset = log.stat().st_size
            world.commands("/" + cmd for cmd in stage_commands(stage))
            actual.extend({"stage": stage, **frame} for frame in
                          frames(log, "HORIZON_CONTROLLER_FRAME ", offset, stage))
    return actual


def angle_delta(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def check(reference, actual):
    expected = {}
    differences = []
    for row in reference:
        key = (row["stage"], row["x"])
        expected.setdefault(key, []).append(row)
    assert len(expected) == len(RIGS) * len(STAGES) and all(len(rows) == 2 for rows in expected.values())

    observed = {}
    for got in actual:
        stage = got["stage"]
        key = (stage, got["x"])
        observed.setdefault(key, []).append(got)
        java = expected[key][0]
        rpm = float(java["rpm"])
        assert (int(java["bracket_vertices"]) > 0) == stage_state(stage, int(got["x"]))[2]
        if int(java["bracket_vertices"]) > 0:
            assert java["body_world_block_light"] != java["above_world_block_light"]
            assert got["body_world_block_light"] != got["above_world_block_light"]
        for name in ("axis", "above", "above_axis", "rpm"):
            if got[name] != java[name]:
                differences.append((key, name, java[name], got[name]))
        for part in ("shaft", "bracket"):
            jcount = int(java[f"{part}_vertices"])
            hcount = int(got[f"{part}_vertices"])
            if jcount != hcount:
                differences.append((key, part + " vertices", jcount, hcount))
            if not jcount:
                continue
            for field in PART_FIELDS[3:]:
                name = f"{part}_{field}"
                if not isclose(float(got[name]), float(java[name]), abs_tol=0.0001):
                    differences.append((key, name, java[name], got[name]))
            for field in ("block_light", "sky_light"):
                name = f"{part}_{field}"
                if got[name] != java[name]:
                    differences.append((key, name, java[name], got[name]))
        time_shift = float(got["render_time"]) - float(java["render_time"])
        angle = float(java["angle"]) + time_shift * rpm * 0.3
        error = angle_delta(float(got["angle"]), angle)
        if abs(error) > 0.003:
            differences.append((key, "angle error", 0.0, error))

    assert expected.keys() == observed.keys()
    for group in (expected, observed):
        fractions = {float(row["fraction"]) for rows in group.values() for row in rows}
        assert len(fractions) > 1 and all(0.0 <= fraction <= 1.0 for fraction in fractions), fractions
        for (stage, x), (first, second) in group.items():
            span = float(second["render_time"]) - float(first["render_time"])
            turn = float(second["angle"]) - float(first["angle"])
            assert span > 0.0 and abs(angle_delta(turn, 0)) > 0.01, (stage, x, first, second)
            assert abs(angle_delta(turn, float(first["rpm"]) * span * 0.3)) <= 0.003
    if differences:
        raise RuntimeError(f"{len(differences)} render differences. First 24: {differences[:24]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda p: Path(p).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/rotation-speed-controller-render-horizon.csv")
    parser.add_argument("--capture-only", action="store_true")
    args = parser.parse_args()
    actual = replay(args)
    with args.output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, ("stage", *FIELDS))
        writer.writeheader()
        writer.writerows(actual)
    if not args.capture_only:
        with (ROOT / "fixtures/rotation-speed-controller-render-java.csv").open() as stream:
            check(list(csv.DictReader(stream)), actual)
        print(f"Controller shaft motion and bracket geometry/light matched {len(actual)} actual submissions.")


if __name__ == "__main__":
    main()
