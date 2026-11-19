#!/usr/bin/env python3
"""Place a cogwheel as a player, reopen the world, and capture the rendered block."""

import argparse
import json
from pathlib import Path
from shutil import copy2
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def check_cogwheel(block):
    identity, _, attributes = block.get("state", "").partition("[")
    properties = dict(entry.split("=", 1) for entry in attributes.rstrip("]").split(",") if entry)
    if (not block.get("loaded") or identity != "create:cogwheel"
            or properties.get("axis") != "y" or properties.get("waterlogged", "false") != "false"):
        raise RuntimeError(f"expected a dry vertical cogwheel, got {block}")


def smoke(args, scratch, screenshot):
    socket = scratch / "ctl.sock"
    game = scratch / "game"
    mods = game / "horizon-mods"
    mods.mkdir(parents=True)
    copy2(ROOT / ".local/create.hmod", mods / "create.hmod")
    (game / "horizon-mods.txt").write_text("mod.create:true\n", encoding="utf-8")

    def ctl(*arguments):
        command = [str(args.ctl.resolve()), "--socket", str(socket), *map(str, arguments)]
        result = json.loads(subprocess.check_output(command, text=True))
        if result.get("ok") is False:
            raise RuntimeError(f"{arguments[0]} failed: {result}")
        return result

    def launch():
        ctl(
            "launch", "--offscreen", "--game", args.client.resolve(),
            "--resources", args.resources.resolve(), "--world", "Cogwheel",
            "--creative", "--wait", "--game-dir", game, "--home", game,
            "--test-terrain", "--render-distance", 4,
        )

    def stop():
        ctl("quit")
        deadline = time.monotonic() + 10
        while socket.exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("Horizon did not close its control socket after quit")
            time.sleep(0.1)

    launch()
    try:
        ctl("command", "/fill 3 92 -12 13 92 -3 minecraft:smooth_stone")
        ctl("command", "/setblock 9 93 -6 minecraft:smooth_stone")
        granted = ctl("command", "/give @s create:cogwheel")
        deadline = time.monotonic() + 5
        while (counts := ctl("inventory")["counts"]).get("create:cogwheel") != 1:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"expected one cogwheel in inventory, got {counts}; give returned {granted}")
            ctl("wait", 1)
        ctl("tp", 7.5, 93, -9.5)
        ctl("wait", 8)
        placed = ctl("place", 9, 94, -6, "--item", "create:cogwheel")
        if not placed.get("changed"):
            raise RuntimeError(f"player placement did not change the block: {placed}")
        check_cogwheel(ctl("block", 9, 94, -6))
    finally:
        stop()

    launch()
    try:
        check_cogwheel(ctl("block", 9, 94, -6))
        ctl("look-at", 9.5, 94.5, -5.5)
        ctl("wait", 20)
        ctl("screenshot", screenshot)
        if screenshot.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"invalid screenshot: {screenshot}")
        print(f"Cogwheel placed and preserved after restart. Inspect {screenshot} for texture parity.")
    finally:
        stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ctl", type=Path)
    parser.add_argument("client", type=Path)
    parser.add_argument("resources", type=Path)
    args = parser.parse_args()
    screenshot = ROOT / ".local/cogwheel.png"
    if not (ROOT / ".local/create.hmod").is_file():
        parser.error("run tools/prepare.py before the smoke test")
    with tempfile.TemporaryDirectory(prefix="hc-") as scratch:
        smoke(args, Path(scratch), screenshot)


if __name__ == "__main__":
    main()
