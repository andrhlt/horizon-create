#!/usr/bin/env python3
"""Run Create's original wheat milling structure in Horizon and compare its Java trace."""

import argparse
import csv
import json
import os
from pathlib import Path
from shutil import copy2
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = (3, 96, -12)
STRUCTURE = "gametest/processing/wheat_milling"
FIELDS = ("tick", "barrel_wheat", "hopper_flour", "chest_flour", "mill_timer", "mill_rpm")


def read_trace(log):
    return [line.split("CREATE_WHEAT ", 1)[1].split() for line in log.splitlines()
            if "CREATE_WHEAT " in line]


def run(args, scratch, expected):
    socket = scratch / "ctl.sock"
    game = scratch / "game"
    logfile = scratch / "ctl.log"
    mods = game / "horizon-mods"
    mods.mkdir(parents=True)
    copy2(args.pack, mods / "create.hmod")
    (game / "horizon-mods.txt").write_text("mod.create:true\n", encoding="utf-8")
    template = Path(STRUCTURE + ".nbt")
    saved_template = game / "saves/Wheat/generated/create/structures" / template
    saved_template.parent.mkdir(parents=True)
    copy2(ROOT / ".local/fixtures/data/create/structure" / template, saved_template)

    env = dict(os.environ, CREATE_WHEAT_TRACE_ORIGIN=",".join(map(str, ORIGIN)),
               CREATE_WHEAT_TRACE_SEED="2")

    def ctl(*arguments):
        command = [str(args.ctl.resolve()), "--socket", str(socket), *map(str, arguments)]
        process = subprocess.run(command, text=True, env=env, capture_output=True)
        if process.returncode:
            raise RuntimeError(f"{arguments[0]} failed: {process.stdout} {process.stderr}")
        result = json.loads(process.stdout)
        if result.get("ok") is False:
            raise RuntimeError(f"{arguments[0]} failed: {result}")
        return result

    ctl("launch", "--headless", "--game", args.client.resolve(), "--resources", args.resources.resolve(),
        "--world", "Wheat", "--creative", "--wait", "--game-dir", game, "--home", game,
        "--test-terrain", "--render-distance", 4)
    try:
        ctl("command", "/tick freeze")
        ctl("command", f"/place template create:{STRUCTURE} {' '.join(map(str, ORIGIN))}")
        expected_blocks = {
            "create:creative_motor": 1,
            "create:cogwheel": 1,
            "create:millstone": 1,
            "create:smart_chute": 1,
            "create:brass_casing": 12,
        }
        deadline = time.monotonic() + 5
        while True:
            counts = ctl("blocks", 3, 96, -12, 6, 102, -10)["counts"]
            if all(counts.get(block) == count for block, count in expected_blocks.items()):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(f"fixture blocks did not load: {counts}")
            time.sleep(0.05)
        lever = ctl("block", 4, 102, -11)
        if lever["state"] != "minecraft:lever[face=wall,facing=west,powered=true]":
            raise RuntimeError(f"unexpected initial lever state: {lever}")
        ctl("command", "/setblock 4 102 -11 minecraft:lever[face=wall,facing=west,powered=false]")
        # Allow the frozen server to observe tick zero before any machine ticks.
        deadline = time.monotonic() + 5
        while not read_trace(logfile.read_text(encoding="utf-8")):
            if time.monotonic() >= deadline:
                raise RuntimeError("Horizon did not observe the starting tick")
            time.sleep(0.05)
        ctl("command", f"/tick step {len(expected) - 1}")
        deadline = time.monotonic() + 15
        while len(read_trace(logfile.read_text(encoding="utf-8"))) < len(expected):
            if time.monotonic() > deadline:
                break
            time.sleep(0.05)
    finally:
        ctl("quit")
        deadline = time.monotonic() + 10
        while socket.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        if logfile.is_file():
            log = logfile.read_text(encoding="utf-8")
            (ROOT / ".local/horizon-wheat.log").write_text(log, encoding="utf-8")
            actual = read_trace(log)

    output = ROOT / ".local/wheat_milling-horizon.csv"
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(FIELDS)
        writer.writerows(actual)
    differences = [(java, horizon) for java, horizon in zip(expected, actual) if java != horizon]
    if len(actual) != len(expected) or differences:
        raise SystemExit(f"Wheat mismatch: {len(differences)} differing rows, "
                         f"Java {len(expected)} rows, Horizon {len(actual)}. "
                         f"First differing rows (Java, Horizon): {differences[:4]}. See {output}")
    print(f"Wheat milling matched Java for all {len(actual)} ticks. See {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ctl", type=Path)
    parser.add_argument("client", type=Path)
    parser.add_argument("resources", type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()
    with (ROOT / "fixtures/wheat_milling-java.csv").open(encoding="utf-8") as file:
        expected = list(csv.reader(file))[1:]
    with tempfile.TemporaryDirectory(prefix="hc-wheat-") as scratch:
        run(args, Path(scratch), expected)


if __name__ == "__main__":
    main()
