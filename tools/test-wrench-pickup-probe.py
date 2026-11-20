#!/usr/bin/env python3
"""Repeat the three initial gearbox Wrench pickup mismatches without retries."""

import argparse
import json
from pathlib import Path

from fixture_world import ROOT, fixture_world

POSITION = (8, 180, 23)
APPROACH = {
    "east": (10.5, 179.0, 23.5),
    "south": (8.5, 179.0, 25.5),
    "west": (6.5, 179.0, 23.5),
}
CASES = (
    ("x-south-to-y", "x", "south", "create:gearbox"),
    ("x-west-to-x", "x", "west", "create:vertical_gearbox"),
    ("y-east-to-z", "y", "east", "create:vertical_gearbox"),
)
REPETITIONS = 3


def state(control):
    return control.call("block", *POSITION)["state"]


def run(args):
    rows = []
    with fixture_world(args, "Wrench-pickup-probe", render=True, pack=args.pack) as control:
        control.commands((
            "/setblock 8 176 23 minecraft:smooth_stone",
            "/setblock 9 181 23 minecraft:smooth_stone",
            "/setblock 8 178 21 minecraft:smooth_stone",
            "/setblock 8 178 25 minecraft:smooth_stone",
            "/setblock 6 178 23 minecraft:smooth_stone",
            "/setblock 10 178 23 minecraft:smooth_stone",
            "/gamemode survival",
        ))
        for case, initial_axis, rotate_face, expected_item in CASES:
            for repetition in range(1, REPETITIONS + 1):
                control.commands((
                    "/clear @s",
                    "/item replace entity @s hotbar.0 with create:wrench",
                    f"/setblock {' '.join(map(str, POSITION))} create:gearbox[axis={initial_axis}]",
                    f"/tp @s {' '.join(map(str, APPROACH[rotate_face]))}",
                ))
                control.call("select", "create:wrench")
                control.call("wait", 3)
                rotation_result = control.call("interact", *POSITION, rotate_face)
                control.call("wait", 3)
                rotated_state = state(control)

                control.command(f"/tp @s {' '.join(map(str, APPROACH['west']))}")
                control.call("wait", 3)
                control.call("key", "shift", "down")
                try:
                    control.call("wait", 4)
                    crouching = control.call("state")["player"]["sneaking"]
                    control.call("look-at", *(coordinate + 0.5 for coordinate in POSITION))
                    if args.aim_wait:
                        control.call("wait", args.aim_wait)
                    ray = control.call("looking-at")
                    pickup_result = control.call("mouse", "right", "click")
                    control.call("wait", 3)
                    after_state = state(control)
                    inventory = control.call("inventory")["counts"]
                finally:
                    control.call("key", "shift", "up")

                hit = ray.get("block") or {}
                returned = {item: count for item, count in inventory.items() if item != "create:wrench"}
                row = {
                    "case": case,
                    "repetition": repetition,
                    "initial_axis": initial_axis,
                    "rotation_face": rotate_face,
                    "aim_wait_frames": args.aim_wait,
                    "rotation_interaction": rotation_result,
                    "rotated_state": rotated_state,
                    "crouching": crouching,
                    "ray_kind": ray.get("kind"),
                    "ray_pos": hit.get("pos"),
                    "ray_face": hit.get("face"),
                    "ray_state": hit.get("state"),
                    "pickup_interaction": pickup_result,
                    "post_pickup_state": after_state,
                    "returned_items": returned,
                    "expected_item": expected_item,
                    "wrench_count": inventory.get("create:wrench", 0),
                }
                row["passed"] = (
                    row["rotated_state"].startswith("create:gearbox[axis=")
                    and row["crouching"] is True
                    and row["ray_kind"] == "block"
                    and row["ray_pos"] == list(POSITION)
                    and row["ray_face"] == "west"
                    and row["post_pickup_state"] == "minecraft:air"
                    and row["returned_items"] == {expected_item: 1}
                    and row["wrench_count"] == 1
                )
                rows.append(row)
                print(json.dumps(row, sort_keys=True))

    output = ROOT / f".local/wrench-pickup-probe-{args.aim_wait}-frame-wait.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    failures = [row for row in rows if not row["passed"]]
    if failures:
        raise RuntimeError(f"{len(failures)}/{len(rows)} observed pickup failures; details: {output}")
    print(f"All {len(rows)} targeted gearbox pickups passed; observations: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ctl", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("client", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("resources", type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--aim-wait", type=int, default=1,
                        help="client frames to wait after aiming before recording the ray and clicking")
    run(parser.parse_args())
