#!/usr/bin/env python3
"""Replay Create's original threshold_switch GameTest in Horizon."""

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
TEMPLATE = Path("gametest/items/threshold_switch.nbt")
CHEST = "4 97 -11"
SWITCH = "5 97 -11"
LAMP = "5 98 -11"


def run(args, scratch, header, expected):
    socket = scratch / "ctl.sock"
    game = scratch / "game"
    mods = game / "horizon-mods"
    mods.mkdir(parents=True)
    copy2(ROOT / ".local/create.hmod", mods / "create.hmod")
    (game / "horizon-mods.txt").write_text("mod.create:true\n")
    saved = game / "saves/Threshold/generated/create/structures" / TEMPLATE
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

    def sample(tick):
        tag, lamp = command_commands((
            f"/data get block {SWITCH}",
            f"/execute if block {LAMP} minecraft:redstone_lamp[lit=true]",
        ))
        message = tag["chat"][-1]
        if "create:stockpile_switch" not in message:
            raise RuntimeError(f"Missing threshold switch at {SWITCH}: {message}")
        values = []
        for key in ("CurrentAmount", "CurrentMaxAmount", "Powered", "PoweredAfterDelay"):
            match = re.search(rf"\b{key}: (-?\d+)", message)
            if not match and tick != 0:
                raise RuntimeError(f"Missing {key} at {SWITCH}: {message}")
            values.append(match[1] if match else "0")
        lamp_message = lamp["chat"][-1]
        if not any(expected in lamp_message for expected in ("Test passed", "Test failed")):
            raise RuntimeError(f"Could not read fixture lamp: {lamp_message}")
        return [*values, "1" if "Test passed" in lamp_message else "0"]

    def fill_chest(stack, slots):
        replies = command_commands(f"/item replace block {CHEST} container.{slot} with {stack}" for slot in slots)
        if any("Replaced 1 slot" not in reply["chat"][-1] for reply in replies):
            raise RuntimeError(f"Could not fill fixture chest: {replies}")

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
        "--world", "Threshold", "--creative", "--wait", "--game-dir", game,
        "--home", game, "--test-terrain", "--render-distance", 4)
    try:
        ctl("command", "/tick freeze")
        ctl("command", "/place template create:gametest/items/threshold_switch 3 96 -12")
        fill_chest("minecraft:diamond 64", range(18))
        start = clock()
        for tick in range(len(expected)):
            if tick:
                step_to(start + tick)
            actual.append([str(tick), *sample(tick)])
            if tick == 7:
                result = ctl("command", f"/data merge block {SWITCH} {{OnAboveAmount:128,OffBelowAmount:64}}")
                if "Modified block data" not in result["chat"][-1]:
                    raise RuntimeError(f"Could not configure switch: {result}")
            elif tick == 14:
                fill_chest("minecraft:air", range(18))
            elif tick in (31, 42):
                fill_chest("minecraft:diamond 64", [int(tick == 42)])
        ctl("command", "/fill 3 96 -16 6 96 -13 minecraft:smooth_stone")
        ctl("tp", 5.5, 97, -14.5)
        ctl("look-at", 4.5, 98.1, -11.5)
        ctl("wait", 3)
        ctl("screenshot", ROOT / ".local/threshold_switch.png")
    finally:
        ctl("quit")
        end = time.monotonic() + 10
        while socket.exists() and time.monotonic() < end:
            time.sleep(0.05)
        (ROOT / ".local/horizon-threshold-switch.log").write_text((scratch / "ctl.log").read_text())

    output = ROOT / ".local/threshold_switch-horizon.csv"
    with output.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    diffs = [(a, b) for a, b in zip(expected, actual) if a != b]
    if diffs:
        raise SystemExit(f"Threshold switch fixture mismatch in {len(diffs)} rows. "
                         f"First (Java, Horizon): {diffs[:5]}")
    print(f"Threshold switch matched Java for all {len(actual)} ticks. See {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve())
    args = parser.parse_args()
    with (ROOT / "fixtures/threshold_switch-java.csv").open() as f:
        rows = csv.reader(f)
        header, expected = next(rows), list(rows)
    with tempfile.TemporaryDirectory(prefix="hc-threshold-") as tmp:
        run(args, Path(tmp), header, expected)


if __name__ == "__main__":
    main()
