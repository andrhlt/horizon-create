#!/usr/bin/env python3
"""Replay the pinned Java source/flowing lava contact matrix in Horizon."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

from fixture_world import ROOT, fixture_world

Y = 170
X_BASE = 8
Z_BASE = 20
PHASE_TICKS = (1, 24, 25, 26, 50)


def coordinates(case_id, side):
    lane_x = 1 + (case_id % 4) * 4
    lane_z = 1 + (case_id // 4) * 4
    left_x = X_BASE + lane_x + 1
    z = Z_BASE + lane_z + 1
    return (left_x if side == "lava" else left_x + 1, Y, z)


def block_state(block_id, state):
    return block_id + state.split("}", 1)[1]


def snapshot(world, rows, phase, tick):
    selected = [row for row in rows if row["phase"] == phase and int(row["tick"]) == tick]
    script = "".join(
        f"block {coordinates(int(row['case_id']), row['side'])[0]} {Y} {coordinates(int(row['case_id']), row['side'])[2]}\n" for row in selected
    )
    blocks = world.call("script", script=script) if selected else []
    return [(row, block) for row, block in zip(selected, blocks, strict=True)]


def run(args):
    with (ROOT / "fixtures/lava-contact-java.csv").open(newline="") as stream:
        expected = list(csv.DictReader(stream))
    if len(expected) != 224:
        raise RuntimeError(f"Expected 224 Java rows, found {len(expected)}")

    cases = {}
    for row in expected:
        case_id = int(row["case_id"])
        cases.setdefault(case_id, row)
    trace = []
    mismatches = []
    env = {"HORIZON_NO_AUDIO": "1"}
    with fixture_world(args, "LavaContact", pack=args.pack, env=env) as world:
        setup = []
        first_fluids = []
        second_fluids = []
        for case_id, row in sorted(cases.items()):
            left_x, _, z = coordinates(case_id, "lava")
            right_x = left_x + 1
            setup.extend((
                f"/fill {left_x - 1} {Y - 1} {z} {right_x + 1} {Y - 1} {z} minecraft:stone",
                f"/fill {left_x - 1} {Y} {z - 1} {right_x + 1} {Y} {z - 1} minecraft:stone",
                f"/fill {left_x - 1} {Y} {z + 1} {right_x + 1} {Y} {z + 1} minecraft:stone",
                f"/setblock {left_x - 1} {Y} {z} minecraft:stone",
                f"/setblock {right_x + 1} {Y} {z} minecraft:stone",
            ))
            liquid_id = f"create:{row['liquid']}"
            liquid_level = 0 if row["special_is_source"] == "true" else 12
            lava_id = "minecraft:lava"
            lava_level = 0 if row["lava_is_source"] == "true" else 12
            liquid_block = f"{liquid_id}[level={liquid_level}]"
            lava_block = f"{lava_id}[level={lava_level}]"
            if row["placement_order"] == "lava_first":
                first_fluids.append(f"/setblock {left_x} {Y} {z} {lava_block}")
                second_fluids.append(f"/setblock {right_x} {Y} {z} {liquid_block}")
            else:
                first_fluids.append(f"/setblock {right_x} {Y} {z} {liquid_block}")
                second_fluids.append(f"/setblock {left_x} {Y} {z} {lava_block}")

        start = world.clock()
        world.commands((*setup, *first_fluids))
        if world.clock() != start:
            raise RuntimeError("Game time advanced during setup before-contact sampling")

        def record_phase(phase, tick):
            for row, block in snapshot(world, expected, phase, tick):
                want_block = row["block_id"]
                want_state = block_state(want_block, row["block_state"])
                matched = (block["block"], block["state"]) == (want_block, want_state)
                result = {
                    **row,
                    "actual_x": coordinates(int(row["case_id"]), row["side"])[0],
                    "actual_z": coordinates(int(row["case_id"]), row["side"])[2],
                    "actual_block": block["block"],
                    "actual_state": block["state"],
                    "matched": matched,
                }
                trace.append(result)
                if not matched:
                    mismatches.append((row["case_id"], row["liquid"], row["lava_kind"], row["placement_order"], phase, tick,
                                       row["side"], want_state, block["state"]))

        record_phase("precontact", 0)
        world.commands(second_fluids)
        record_phase("immediate", 0)
        replay_start = world.clock()
        print(f"Contact replay start {replay_start} (initial frozen time {start}).", flush=True)
        last_step = replay_start
        for tick in PHASE_TICKS:
            target = replay_start + tick
            for step in range(last_step + 1, target + 1):
                world.step_to(step)
            last_step = target
            record_phase("scheduled", tick)

    fields = list(expected[0]) + ["actual_x", "actual_z", "actual_block", "actual_state", "matched"]
    with args.trace.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(trace)
    print(f"Captured {len(trace)} Horizon samples against {len(expected)} Java rows; {len(mismatches)} block/state mismatches.")
    for mismatch in mismatches[:20]:
        print("MISMATCH", *mismatch)
    if mismatches and not args.allow_mismatch:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--trace", type=Path, default=ROOT / ".local/lava-contact-horizon.csv")
    parser.add_argument("--allow-mismatch", action="store_true")
    run(parser.parse_args())
