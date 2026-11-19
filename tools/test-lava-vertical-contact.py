#!/usr/bin/env python3
"""Replay the pinned Java vertical lava-contact and falling-flow trace."""
import argparse
import csv
from pathlib import Path

from fixture_world import ROOT, fixture_world

Y = 170
X_BASE = 8
Z_BASE = 20
SAMPLE_TICKS = (1, 29, 30, 31, 59, 60, 61)


def position(row):
    return (
        X_BASE + int(row["relative_x"]),
        Y + int(row["relative_y"]) - 2,
        Z_BASE + int(row["relative_z"]),
    )


def state_for(row):
    return row["block_id"] + row["block_state"].split("}", 1)[1]


def snapshot(world, expected, phase, tick):
    selected = [row for row in expected if row["phase"] == phase and int(row["tick"]) == tick]
    script = "".join(f"block {x} {y} {z}\n" for x, y, z in (position(row) for row in selected))
    actual = world.call("script", script=script) if selected else []
    return zip(selected, actual, strict=True)


def run(args):
    with (ROOT / "fixtures/lava-vertical-contact-java.csv").open(newline="") as stream:
        expected = list(csv.DictReader(stream))
    if len(expected) != 360:
        raise RuntimeError(f"Expected 360 Java rows, found {len(expected)}")
    cases = {}
    for row in expected:
        cases.setdefault(int(row["case_id"]), row)

    trace = []
    mismatches = []
    with fixture_world(args, "LavaVerticalContact", pack=args.pack, env={"HORIZON_NO_AUDIO": "1"}) as world:
        setup, first, second = [], [], []
        for case_id, row in sorted(cases.items()):
            x = X_BASE + 2 + (case_id % 4) * 4
            z = Z_BASE + 2 + (case_id // 4) * 4
            lava_y = Y + (1 if row["orientation"] == "lava_above" else 0 if row["orientation"] == "lava_below" else 2)
            special_y = Y + (1 if row["orientation"] == "lava_below" else 0)
            setup.extend((
                f"/fill {x - 1} {Y - 1} {z - 1} {x - 1} {Y + 2} {z + 1} minecraft:stone",
                f"/fill {x + 1} {Y - 1} {z - 1} {x + 1} {Y + 2} {z + 1} minecraft:stone",
                f"/fill {x} {Y - 1} {z - 1} {x} {Y + 2} {z - 1} minecraft:stone",
                f"/fill {x} {Y - 1} {z + 1} {x} {Y + 2} {z + 1} minecraft:stone",
                f"/setblock {x} {Y - 1} {z} minecraft:stone",
            ))
            liquid_level = 0 if row["special_is_source"] == "true" else 12
            liquid = f"create:{row['liquid']}[level={liquid_level}]"
            lava = "minecraft:lava[level=0]"
            if row["placement_order"] == "lava_first":
                first.append(f"/setblock {x} {lava_y} {z} {lava}")
                second.append(f"/setblock {x} {special_y} {z} {liquid}")
            else:
                first.append(f"/setblock {x} {special_y} {z} {liquid}")
                second.append(f"/setblock {x} {lava_y} {z} {lava}")

        world.commands((*setup, *first))
        record(world, expected, trace, mismatches, "precontact", 0)
        world.commands(second)
        record(world, expected, trace, mismatches, "immediate", 0)
        replay_start = world.clock()
        last_step = replay_start
        for tick in SAMPLE_TICKS:
            target = replay_start + tick
            for step in range(last_step + 1, target + 1):
                world.step_to(step)
            last_step = target
            record(world, expected, trace, mismatches, "scheduled", tick)

    fields = list(expected[0]) + ["actual_x", "actual_y", "actual_z", "actual_block", "actual_state", "matched"]
    with args.trace.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(trace)
    print(f"Captured {len(trace)} Horizon samples against {len(expected)} Java rows; {len(mismatches)} block/state mismatches.")
    for mismatch in mismatches[:24]:
        print("MISMATCH", *mismatch)
    if mismatches and not args.allow_mismatch:
        raise SystemExit(1)


def record(world, expected, trace, mismatches, phase, tick):
    for row, block in snapshot(world, expected, phase, tick):
        want_block = row["block_id"]
        want_state = state_for(row)
        matched = (block["block"], block["state"]) == (want_block, want_state)
        x, y, z = position(row)
        result = {
            **row,
            "actual_x": x,
            "actual_y": y,
            "actual_z": z,
            "actual_block": block["block"],
            "actual_state": block["state"],
            "matched": matched,
        }
        trace.append(result)
        if not matched:
            mismatches.append((row["case_id"], row["liquid"], row["orientation"], row["special_is_source"],
                               row["placement_order"], phase, tick, row["side"], want_state, block["state"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--trace", type=Path, default=ROOT / ".local/lava-vertical-contact-horizon.csv")
    parser.add_argument("--allow-mismatch", action="store_true")
    run(parser.parse_args())
