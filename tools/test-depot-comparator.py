#!/usr/bin/env python3
"""Replay Create's original depot_comparator_output GameTest in Horizon."""

import argparse
import csv
import json
from pathlib import Path
import re
from shutil import copy2
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path("gametest/items/depot_comparator_output.nbt")
DEPOT = "4 97 -9"
SAMPLES = tuple((f"{x} 97 {z}", key) for x in (4, 6, 8, 10)
                for z, key in ((-10, "OutputSignal"), (-11, "RedstoneStrength")))


def run(args, scratch, header, expected):
    socket = scratch / "ctl.sock"
    game = scratch / "game"
    mods = game / "horizon-mods"
    mods.mkdir(parents=True)
    copy2(ROOT / ".local/create.hmod", mods / "create.hmod")
    (game / "horizon-mods.txt").write_text("mod.create:true\n")
    saved = game / "saves/Depots/generated/create/structures" / TEMPLATE
    saved.parent.mkdir(parents=True)
    copy2(ROOT / ".local/fixtures/data/create/structure" / TEMPLATE, saved)

    def ctl(*arguments, script=None):
        result = subprocess.run(
            [str(args.ctl), "--socket", str(socket), *map(str, arguments)],
            input=script, text=True, capture_output=True, timeout=45,
        )
        if result.returncode != 0:
            raise RuntimeError(f"{arguments} failed: {result.stdout} {result.stderr}")
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        if not replies or any(reply.get("ok") is False for reply in replies):
            raise RuntimeError(f"{arguments} failed: {replies}")
        return replies if script is not None else replies[-1]

    def command_commands(commands):
        return ctl("script", script="".join(f"command {json.dumps(cmd)}\n" for cmd in commands))

    def sample():
        tags = command_commands(f"/data get block {pos}" for pos, _ in SAMPLES)
        values = []
        for response, (pos, key) in zip(tags, SAMPLES, strict=True):
            message = response["chat"][-1]
            match = re.search(rf"\b{key}: (\d+)", message)
            if not match:
                raise RuntimeError(f"Missing {key} at {pos} in {message}")
            values.append(match[1])
        return values

    def clock():
        result = ctl("command", "/time query gametime")["chat"][-1]
        return int(re.search(r"(\d+) tick", result)[1])

    def step_to(tick):
        ctl("command", "/tick step 1")
        end = time.monotonic() + 4
        while clock() < tick:
            if time.monotonic() >= end:
                raise RuntimeError(f"World did not advance to tick {tick}")

    actual = []
    ctl("launch", "--offscreen", "--game", args.client, "--resources", args.resources,
        "--world", "Depots", "--creative", "--wait", "--game-dir", game,
        "--home", game, "--test-terrain", "--render-distance", 4)
    try:
        ctl("command", "/tick freeze")
        ctl("command", "/place template create:gametest/items/depot_comparator_output 3 96 -12")
        start = clock()
        for tick in range(1, 7):
            step_to(start + tick)
        start = clock()
        for tick in range(len(expected)):
            if tick:
                step_to(start + tick)
            actual.append([str(tick), *sample()])
            if tick in (0, 8):
                item = "minecraft:air" if tick == 0 else "minecraft:ender_pearl 4"
                message = ctl("command", f"/item replace block {DEPOT} container.0 with {item}")
                print(message["chat"][-1], flush=True)
        ctl("command", "/fill 3 96 -16 11 96 -13 minecraft:smooth_stone")
        ctl("tp", 7.5, 97, -14.5)
        ctl("look-at", 7.5, 98.1, -10.5)
        ctl("wait", 3)
        ctl("screenshot", ROOT / ".local/depot_comparator_output.png")
    finally:
        ctl("quit")
        end = time.monotonic() + 10
        while socket.exists() and time.monotonic() < end:
            time.sleep(0.05)
        (ROOT / ".local/horizon-depot-comparator.log").write_text((scratch / "ctl.log").read_text())

    output = ROOT / ".local/depot_comparator_output-horizon.csv"
    with output.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    diffs = [(a, b) for a, b in zip(expected, actual) if a != b]
    if diffs:
        raise SystemExit(f"Depot fixture mismatch in {len(diffs)} rows. "
                         f"First (Java, Horizon): {diffs[:5]}")
    print(f"Depot comparator output matched Java for all {len(actual)} ticks. See {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve())
    args = parser.parse_args()
    with (ROOT / "fixtures/depot_comparator_output-java.csv").open() as f:
        rows = csv.reader(f)
        header, expected = next(rows), list(rows)
    with tempfile.TemporaryDirectory(prefix="hc-depot-") as tmp:
        run(args, Path(tmp), header, expected)


if __name__ == "__main__":
    main()
