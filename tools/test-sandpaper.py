#!/usr/bin/env python3
"""Compare the authoritative sandpaper item-use ticks with Java's use, release, and finish."""
import argparse
import csv
import json
from pathlib import Path
import time

from fixture_world import ROOT, fixture_world

STRUCTURE = Path("gametest/misc/threshold_switch_pulley.nbt")
KEYS = ("input_in_hand", "raw_quartz", "polished_quartz", "damage", "polishing")


def setup(control, trial):
    paper = "create:red_sand_paper" if trial == 2 else "create:sand_paper"
    first, second = (("create:rose_quartz", 2), (paper, 1)) if trial == 2 else ((paper, 1), ("create:rose_quartz", 2))
    control.call("script", script="\n".join(
        f'command "{cmd}"' for cmd in (
            "/clear @s",
            f"/item replace entity @s hotbar.0 with {first[0]} {first[1]}",
            f"/item replace entity @s weapon.offhand with {second[0]} {second[1]}",
        )
    ) + "\n")
    control.call("key", "1", "tap")
    control.call("wait", 3)
    control.call("mouse", "right", "down")


def events(path):
    if not path.exists():
        return []
    payload = path.read_text()
    return [json.loads(line) for line in payload[:payload.rfind("\n") + 1].splitlines()]


def wait_for(path, condition, seconds=35):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        rows = events(path)
        if condition(rows):
            return rows
        time.sleep(0.01)
    raise RuntimeError(f"Timed out on the server's sandpaper item use: {events(path)[-6:]}")


def selected(rows, trial):
    section = []
    for row in rows:
        if row["event"] == "start" and section:
            break
        section.append(row)
        if row["event"] == ("release" if trial == 1 else "finish"):
            break
    return section


def action_setup(control, paper, paper_hand, quartz_count=2, other_item=None):
    main = paper if paper_hand == "main" else (other_item or "create:rose_quartz")
    offhand = paper if paper_hand == "offhand" else other_item
    if paper_hand == "main":
        offhand = other_item or "create:rose_quartz"
    else:
        main = other_item or "create:rose_quartz"
    commands = [
        "/clear @s",
        f"/item replace entity @s hotbar.0 with {main} {quartz_count if main == 'create:rose_quartz' else 1}",
    ]
    if offhand and offhand != "minecraft:air":
        commands.append(
            f"/item replace entity @s weapon.offhand with {offhand} "
            f"{quartz_count if offhand == 'create:rose_quartz' else 1}"
        )
    control.commands(commands)
    control.call("key", "1", "tap")
    control.call("wait", 2)


def inventory_signature(control):
    inventory = control.call("inventory")
    return inventory["counts"], inventory["hotbar"], inventory["offhand"]


def action_cases(control, path):
    passed = 0
    for paper in ("create:sand_paper", "create:red_sand_paper"):
        for hand in ("main", "offhand"):
            first = len(events(path))
            quartz_count = 1 if paper == "create:red_sand_paper" and hand == "offhand" else 2
            action_setup(control, paper, hand, quartz_count=quartz_count)
            control.call("mouse", "right", "down")
            rows = wait_for(path, lambda all_rows: any(
                row["event"] == "finish" for row in all_rows[first:]
            ))
            control.call("mouse", "right", "up")
            control.call("wait", 2)
            if not any(row["event"] == "start" for row in rows[first:]):
                raise RuntimeError(f"{paper} in {hand} hand finished without a start event")
            inventory = control.call("inventory")
            counts = inventory["counts"]
            observed = (
                counts.get("create:rose_quartz", 0),
                counts.get("create:polished_rose_quartz", 0),
                counts.get(paper, 0),
                (inventory["hotbar"][0] if hand == "main" else inventory["offhand"]).get("damage", 0),
            )
            expected = (quartz_count - 1, 1, 1, 1)
            if observed != expected:
                raise RuntimeError(f"{paper} in {hand} hand: expected {expected}, got {observed}")
            passed += 1

    for label, other_item in (("empty", "minecraft:air"), ("invalid item", "minecraft:stone")):
        first = len(events(path))
        action_setup(control, "create:sand_paper", "main", other_item=other_item)
        before = inventory_signature(control)
        control.call("mouse", "right", "down")
        control.call("wait", 2)
        control.call("mouse", "right", "up")
        control.call("wait", 2)
        after = inventory_signature(control)
        rows = events(path)[first:]
        if before != after or any(row["event"] == "start" for row in rows):
            raise RuntimeError(f"Sand Paper consumed or started against {label}: before={before}, after={after}, events={rows}")
        passed += 1

    control.command("/gamemode creative")
    first = len(events(path))
    action_setup(control, "create:sand_paper", "main", quartz_count=1)
    control.call("mouse", "right", "down")
    wait_for(path, lambda all_rows: any(
        row["event"] == "finish" for row in all_rows[first:]
    ))
    control.call("mouse", "right", "up")
    control.call("wait", 2)
    inventory = control.call("inventory")
    creative_result = (
        inventory["counts"].get("create:rose_quartz", 0),
        inventory["counts"].get("create:polished_rose_quartz", 0),
        (inventory["hotbar"][0] or {}).get("damage", 0),
    )
    if creative_result != (0, 1, 0):
        raise RuntimeError(f"Creative polishing expected (0 raw, 1 polished, 0 damage), got {creative_result}")
    control.command("/gamemode survival")
    passed += 1

    action_setup(control, "create:sand_paper", "main", quartz_count=8)
    for _ in range(8):
        first = len(events(path))
        control.call("mouse", "right", "down")
        wait_for(path, lambda all_rows: any(
            row["event"] == "finish" for row in all_rows[first:]
        ))
        control.call("mouse", "right", "up")
        control.call("wait", 5)
    counts = control.call("inventory")["counts"]
    wear_result = (
        counts.get("create:rose_quartz", 0),
        counts.get("create:polished_rose_quartz", 0),
        counts.get("create:sand_paper", 0),
    )
    if wear_result != (0, 8, 0):
        raise RuntimeError(f"Eight uses should consume eight quartz and break one paper: {wear_result}")
    passed += 1
    print(f"Sandpaper player actions passed: {passed} cases (both variants and hands, last-item use, empty/invalid targets, creative durability, and breakage).")


def run(args):
    with (ROOT / "fixtures/sandpaper-java.csv").open() as data:
        expected = {(int(r["trial"]), int(r["tick"])): r for r in csv.DictReader(data)}
    path = ROOT / ".local/sandpaper-events.jsonl"
    path.unlink(missing_ok=True)
    observed = ROOT / ".local/sandpaper-horizon.csv"
    with fixture_world(args, "Sandpaper", STRUCTURE, render=True, pack=args.pack,
                       env={"CREATE_TRACE_SANDPAPER": str(path)}) as control, observed.open("w") as out:
        control.commands((
            "/fill 3 111 -10 9 111 -4 minecraft:smooth_stone",
            "/tp @s 6.5 112 -7.5 90 -10",
            "/gamemode survival",
            "/tick rate 5",
        ))
        control.call("wait", 3)
        writer = csv.writer(out)
        writer.writerow(("trial", "tick", *KEYS))
        count = 0
        for trial in range(3):
            first = len(events(path))
            setup(control, trial)
            if trial == 1:
                wait_for(path, lambda rows: any(r["event"] == "tick" and r["tick"] == 11 for r in rows[first:]))
                control.call("mouse", "right", "up")
            elif args.visual and trial == 0:
                wait_for(path, lambda rows: any(r["event"] == "tick" and r["tick"] == 16 for r in rows[first:]))
                control.call("screenshot", ROOT / ".local/sandpaper.png")
            done = "release" if trial == 1 else "finish"
            rows = wait_for(path, lambda rows: any(r["event"] == done for r in rows[first:]))
            control.call("mouse", "right", "up")
            control.call("wait", 3)
            states = {row["tick"]: row for row in selected(rows[first:], trial)}
            last = 13 if trial == 1 else 32
            for tick in range(last + 1):
                if tick not in states:
                    raise RuntimeError(f"Trial {trial} missed authoritative tick {tick}: {states.keys()}")
                values = tuple(int(states[tick][key]) for key in KEYS[:-1]) + (str(states[tick]["polishing"]).lower(),)
                writer.writerow((trial, tick, *values))
                row = expected[(trial, tick)]
                want = tuple(int(row[key]) for key in KEYS[:-1]) + (row["polishing"],)
                if values != want:
                    raise RuntimeError(f"Trial {trial} tick {tick}: Horizon {values}, Java {want}")
                count += 1
        action_cases(control, path)
    print(f"Sandpaper use through finish or release and durability matched all {count} measured Java ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    parser.add_argument("--pack", type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
