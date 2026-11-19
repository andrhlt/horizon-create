#!/usr/bin/env python3
"""Replay Create's original smart_observer_storage GameTest in Horizon."""

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
def run(args, scratch, header, expected, fixture, columns):
    template = Path(f"gametest/items/{fixture}.nbt")
    socket = scratch / "ctl.sock"
    game = scratch / "game"
    mods = game / "horizon-mods"
    mods.mkdir(parents=True)
    copy2(ROOT / ".local/create.hmod", mods / "create.hmod")
    (game / "horizon-mods.txt").write_text("mod.create:true\n")
    saved = game / "saves/Observer/generated/create/structures" / template
    saved.parent.mkdir(parents=True)
    copy2(ROOT / ".local/fixtures/data/create/structure" / template, saved)

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

    def coordinates(x):
        return (f"{x} 99 -11", f"{x} 98 -11", f"{x} 97 -11", f"{x} 97 -10", f"{x} 97 -9")

    def test_boolean(reply):
        message = reply["chat"][-1]
        if "Test passed" in message:
            return "1"
        if "Test failed" in message:
            return "0"
        raise RuntimeError(f"Invalid block test: {message}")

    def sample(tick, column):
        source, chute, receiver, observer, lamp = coordinates(3 + column)
        replies = command_commands([
            *(f"/data get block {pos}" for pos in (source, chute, receiver)),
            f"/data get block {observer}",
            f"/execute if block {observer} create:content_observer[powered=true]",
            f"/execute if block {lamp} minecraft:redstone_lamp[lit=true]",
        ])
        counts = []
        for reply, block in zip(replies[:3], ("minecraft:chest", "create:smart_chute", "minecraft:chest")):
            message = reply["chat"][-1]
            if block not in message:
                raise RuntimeError(f"Missing {block}: {message}")
            counts.append(str(sum(map(int, re.findall(r"\b(?:count|Count): (\d+)", message)))))
        observer_tag = replies[3]["chat"][-1]
        delay = re.search(r"\bTurnOff: (\d+)", observer_tag)
        if not delay:
            raise RuntimeError(f"Missing TurnOff at {observer}: {observer_tag}")
        return [str(tick), str(column), *counts, test_boolean(replies[4]), delay[1], test_boolean(replies[5])]

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
        "--world", "Observer", "--creative", "--wait", "--game-dir", game,
        "--home", game, "--test-terrain", "--render-distance", 4)
    try:
        ctl("command", "/tick freeze")
        ctl("command", f"/place template create:gametest/items/{fixture} 3 96 -12")
        lever = "5 98 -11" if len(columns) == 2 else "4 98 -10"
        face = "floor" if len(columns) == 2 else "wall"
        ctl("command", f"/setblock {lever} minecraft:lever[face={face},facing=south,powered=false]")
        receiver = coordinates(3 + columns[-1])[2]
        start = clock()
        for tick in range(len(expected) // len(columns)):
            if tick:
                step_to(start + tick)
            actual.extend(sample(tick, column) for column in columns)
            if tick in (15, 34):
                item = "minecraft:air" if tick == 15 else "minecraft:gold_block"
                reply = ctl("command", f"/item replace block {receiver} container.0 with {item}")
                if "Replaced 1 slot" not in reply["chat"][-1]:
                    raise RuntimeError(f"Could not change observed inventory: {reply}")
        ctl("command", "/fill 3 96 -16 8 96 -13 minecraft:smooth_stone")
        ctl("tp", 5.5, 97, -14.5)
        ctl("look-at", 5.5, 97.5, -10.5)
        ctl("wait", 3)
        ctl("screenshot", ROOT / f".local/{fixture}.png")
    finally:
        ctl("quit")
        end = time.monotonic() + 10
        while socket.exists() and time.monotonic() < end:
            time.sleep(0.05)
        (ROOT / f".local/horizon-{fixture}.log").write_text((scratch / "ctl.log").read_text())

    output = ROOT / f".local/{fixture}-horizon.csv"
    with output.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(actual)
    diffs = [(a, b) for a, b in zip(expected, actual) if a != b]
    if diffs:
        raise SystemExit(f"Smart Observer fixture mismatch in {len(diffs)} rows. "
                         f"First (Java, Horizon): {diffs[:5]}")
    print(f"{fixture} matched Java for {len(actual) // len(columns)} ticks across {len(columns)} lane(s). See {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve())
    parser.add_argument("--filtered", action="store_true")
    args = parser.parse_args()
    fixture = "smart_observer_filtered_storage" if args.filtered else "smart_observer_storage"
    columns = (1, 3) if args.filtered else (1,)
    with (ROOT / f"fixtures/{fixture}-java.csv").open() as f:
        rows = csv.reader(f)
        header, expected = next(rows), list(rows)
    with tempfile.TemporaryDirectory(prefix="hc-observer-") as tmp:
        run(args, Path(tmp), header, expected, fixture, columns)


if __name__ == "__main__":
    main()
