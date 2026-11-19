#!/usr/bin/env python3
"""Compare Java food consumption results for a real LAN guest."""
import argparse
import csv
from contextlib import contextmanager
import json
from importlib import import_module
from food_trace import same_f32
from pathlib import Path
from tempfile import TemporaryDirectory
from shutil import copy2

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
GUEST = "FoodGuest"
FOODS = ("sweet_roll", "chocolate_glazed_berries", "honeyed_apple")


def prepare_hunger(host, trace):
    host.commands((
        f"/clear {GUEST}",
        f"/effect give {GUEST} minecraft:instant_health 1 5 true",
        f"/effect give {GUEST} minecraft:hunger 240 15 true",
    ))
    def ready():
        records = [row for row in trace_rows(trace) if row["player"] == GUEST]
        if not records:
            return False
        last = records[-1]
        if last["hunger"] < 10:
            raise AssertionError(f"Hunger setup overshot: {last}")
        return last["hunger"] == 10 and same_f32(last["saturation"], 0)
    multiplayer.until("guest hunger setup", ready, seconds=180)
    host.command(f"/effect clear {GUEST} minecraft:hunger")


def trace_rows(path):
    if not path.exists():
        return []
    # The server writes one complete JSON line per player tick. Ignore only a
    # trailing partial line while it is being written.
    lines = path.read_text().splitlines(keepends=True)
    return [json.loads(line) for line in lines if line.endswith("\n")]


def compare(food, reference, samples):
    for index, (expected, sample) in enumerate(zip(reference, samples, strict=True)):
        if sample["tick"] != samples[0]["tick"] + index or sample["player"] != GUEST:
            raise AssertionError(f"{food}: missing or interleaved player tick at {index}: {sample}")
        remaining = max(0, sample["duration"] - sample["using"]) if sample["using"] is not None else 0
        actual = (sample["item"], sample["count"], remaining, sample["hunger"])
        want = (expected["item"], int(expected["count"]), int(expected["use_remaining"]), int(expected["hunger"]))
        if actual != want or not same_f32(sample["saturation"], expected["saturation"]):
            raise AssertionError(f"{food} player tick {index}: Horizon {sample}; Java {expected}")


@contextmanager
def trace_file():
    with TemporaryDirectory(prefix="hc-food-lan-trace-") as scratch:
        trace = Path(scratch) / "trace.jsonl"
        try:
            yield trace
        finally:
            if trace.exists():
                evidence = ROOT / ".local" / f"food-use-lan-{Path(scratch).name}.jsonl"
                copy2(trace, evidence)
                print(f"Guest tick trace: {evidence}", flush=True)


def run(args):
    with (ROOT / "fixtures/food-use-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    with trace_file() as trace, fixture_world(args, "Food Use LAN", render=True, pack=args.pack,
                       env={"HORIZON_TEST_GUEST_FOOD_TRACE": str(trace)}) as host:
        host.command("/gamerule naturalRegeneration false")
        port = host.call("lan", "open", 0, "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-food-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
            scenario="food-use-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to join", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.command(f"/gamemode survival {GUEST}")
            for food in FOODS:
                reference = [row for row in rows if row["food"] == food]
                if [row["tick"] for row in reference] != [str(tick) for tick in range(36)]:
                    raise AssertionError(f"{food}: incomplete Java trace")
                prepare_hunger(host, trace)
                item = f"create:{food}"
                host.command(f"/item replace entity {GUEST} hotbar.0 with {item}")
                multiplayer.until(f"{food} to reach the guest", lambda: multiplayer.count(guest, item) == 1)
                guest.call("select", item)
                offset = len(trace_rows(trace))
                guest.call("mouse", "right", "down")
                try:
                    def samples():
                        records = [row for row in trace_rows(trace)[offset:] if row["player"] == GUEST]
                        starts = [i for i, row in enumerate(records)
                                  if row["player"] == GUEST and row["item"] == item and row["using"] == 0]
                        if len(starts) > 1:
                            raise AssertionError(f"{food}: duplicate use starts")
                        if starts and len(records) >= starts[0] + len(reference):
                            return records[starts[0]:starts[0] + len(reference)]
                        return None
                    observed = multiplayer.until(f"36 guest player ticks for {food}", samples)
                    compare(food, reference, observed)
                    multiplayer.until(f"consumed {food} to reach the guest",
                                      lambda: multiplayer.count(guest, item) == 0)
                finally:
                    guest.call("mouse", "right", "up")
                print(f"{food}: matched Java over 36 consecutive guest player ticks.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
