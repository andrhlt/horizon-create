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


def run(args):
    with (ROOT / "fixtures/sandpaper-java.csv").open() as data:
        expected = {(int(r["trial"]), int(r["tick"])): r for r in csv.DictReader(data)}
    path = ROOT / ".local/sandpaper-events.jsonl"
    path.unlink(missing_ok=True)
    observed = ROOT / ".local/sandpaper-horizon.csv"
    with fixture_world(args, "Sandpaper", STRUCTURE, render=True,
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
    print(f"Sandpaper use through finish or release and durability matched all {count} measured Java ticks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--visual", action="store_true")
    run(parser.parse_args())
