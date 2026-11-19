#!/usr/bin/env python3
"""Replay Create's original waterwheel_materials GameTest in Horizon."""

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
TEMPLATE = Path("gametest/fluids/waterwheel_materials.nbt")
WHEELS = ("7 97 -10", "6 98 -9")
DEPLOYERS = ("9 97 -10", "9 97 -9")
CHESTS = ("9 99 -10", "9 99 -9")


def run(args, scratch, header, expected, woods):
    socket = scratch / "ctl.sock"
    game = scratch / "game"
    mods = game / "horizon-mods"
    mods.mkdir(parents=True)
    copy2(ROOT / ".local/create.hmod", mods / "create.hmod")
    (game / "horizon-mods.txt").write_text("mod.create:true\n")
    saved = game / "saves/Materials/generated/create/structures" / TEMPLATE
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

    def block_tags():
        tags = command_commands(f"/data get block {pos}" for pos in (*WHEELS, *DEPLOYERS))
        return [response["chat"][-1] for response in tags]

    def field(tag, key):
        result = re.search(rf'\b{key}: ("[^"]+"|[-\d.]+)', tag)
        if not result:
            raise RuntimeError(f"Missing {key} in {tag}")
        return result[1].strip('"')

    def clock():
        result = ctl("command", "/time query gametime")["chat"][-1]
        return int(re.search(r"(\d+) tick", result)[1])

    actual = []
    next_wood = 0
    ctl("launch", "--offscreen", "--game", args.client, "--resources", args.resources,
        "--world", "Materials", "--creative", "--wait", "--game-dir", game,
        "--home", game, "--test-terrain", "--render-distance", 4)
    try:
        ctl("command", "/tick freeze")
        ctl("command", "/place template create:gametest/fluids/waterwheel_materials 3 96 -12")
        ctl("command", "/setblock 8 98 -11 minecraft:lever[face=floor,facing=south,powered=false]")
        start = clock()
        for tick in range(len(expected)):
            if tick:
                ctl("command", "/tick step 1")
                end = time.monotonic() + 4
                while clock() < start + tick:
                    if time.monotonic() >= end:
                        raise RuntimeError(f"World did not advance to fixture tick {tick}")
            small, large, a, b = block_tags()
            materials = (field(small, "Name"), field(large, "Name"))
            row = [str(tick), *materials]
            for tag in (a, b):
                row += [field(tag, "State"), field(tag, "Timer"), field(tag, "Speed")]
            actual.append(row)
            if tick == 3:
                command_commands(
                    f"/item replace block {chest} container.{slot} with {wood}"
                    for chest in CHESTS for slot, wood in enumerate(woods)
                )
            if next_wood < len(woods) and materials == (woods[next_wood],) * 2:
                command_commands(f"/item replace block {pos} container.0 with minecraft:air" for pos in DEPLOYERS)
                next_wood += 1
        ctl("command", "/fill 5 96 -16 9 96 -13 minecraft:smooth_stone")
        ctl("tp", 6.5, 97, -14.5)
        ctl("look-at", 6.5, 98.5, -9.5)
        ctl("wait", 3)
        ctl("screenshot", ROOT / ".local/waterwheel_materials.png")
    finally:
        ctl("quit")
        end = time.monotonic() + 10
        while socket.exists() and time.monotonic() < end:
            time.sleep(0.05)
        (ROOT / ".local/horizon-waterwheel-materials.log").write_text((scratch / "ctl.log").read_text())

    output = ROOT / ".local/waterwheel_materials-horizon.csv"
    with output.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    diffs = [(a, b) for a, b in zip(expected, actual) if a != b]
    if diffs or next_wood != len(woods):
        raise SystemExit(f"Material fixture mismatch in {len(diffs)} rows. "
                         f"Applied {next_wood}/{len(woods)} planks. First (Java, Horizon): {diffs[:5]}")
    print(f"Water-wheel materials matched Java for all {len(actual)} ticks. See {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve())
    args = parser.parse_args()
    with (ROOT / "fixtures/waterwheel_materials-java.csv").open() as f:
        rows = csv.reader(f)
        header, expected = next(rows), list(rows)
    woods = (ROOT / "fixtures/waterwheel_materials-items.txt").read_text().splitlines()
    with tempfile.TemporaryDirectory(prefix="hc-materials-") as tmp:
        run(args, Path(tmp), header, expected, woods)


if __name__ == "__main__":
    main()
