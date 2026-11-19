#!/usr/bin/env python3
"""Place Table Cloth as a player and verify every variant across a restart."""

import argparse
import json
from pathlib import Path
from shutil import copy2
import subprocess
import tempfile
import time

from table_cloths import TABLE_CLOTHS

ROOT = Path(__file__).resolve().parents[1]


def check_cloth(block, name):
    if not block.get("loaded") or block.get("state") != f"create:{name}[entity=false]":
        raise RuntimeError(f"expected {name} with entity=false, got {block}")


def smoke(args, scratch, screenshot):
    socket = scratch / "ctl.sock"
    game = scratch / "game"
    mods = game / "horizon-mods"
    mods.mkdir(parents=True)
    copy2(args.pack, mods / "create.hmod")
    (game / "horizon-mods.txt").write_text("mod.create:true\n", encoding="utf-8")

    def ctl(*arguments):
        command = [str(args.ctl.resolve()), "--socket", str(socket), *map(str, arguments)]
        result = json.loads(subprocess.run(command, text=True, stdout=subprocess.PIPE, check=False).stdout)
        if result.get("ok") is False:
            raise RuntimeError(f"{arguments[0]} failed: {result}")
        return result

    def launch():
        ctl(
            "launch", "--offscreen", "--game", args.client.resolve(),
            "--resources", args.resources.resolve(), "--world", "Table Cloth",
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
        ctl("command", "/fill 0 92 -20 30 92 0 minecraft:smooth_stone")
        for i, name in enumerate(TABLE_CLOTHS):
            ctl("command", f"/setblock {i + 1} 93 -15 create:{name}")
            check_cloth(ctl("block", i + 1, 93, -15), name)
        ctl("command", "/setblock 9 93 -6 minecraft:smooth_stone")
        ctl("command", "/give @s create:red_table_cloth")
        ctl("tp", 7.5, 93, -9.5)
        ctl("wait", 8)
        placed = ctl("place", 9, 94, -6, "--item", "create:red_table_cloth")
        if not placed.get("changed"):
            raise RuntimeError(f"player placement did not change the block: {placed}")
        check_cloth(ctl("block", 9, 94, -6), "red_table_cloth")
    finally:
        stop()

    launch()
    try:
        for i, name in enumerate(TABLE_CLOTHS):
            check_cloth(ctl("block", i + 1, 93, -15), name)
        check_cloth(ctl("block", 9, 94, -6), "red_table_cloth")
        ctl("look-at", 9.5, 94.1, -5.5)
        ctl("wait", 20)
        ctl("screenshot", screenshot)
        if screenshot.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"invalid screenshot: {screenshot}")
        print(f"All 19 Table Cloth variants survived restart; player placement succeeded. Screenshot: {screenshot}")
    finally:
        stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ctl", type=Path)
    parser.add_argument("client", type=Path)
    parser.add_argument("resources", type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    args = parser.parse_args()
    screenshot = ROOT / ".local/table-cloth.png"
    if not args.pack.is_file():
        parser.error("run tools/prepare.py before the smoke test")
    with tempfile.TemporaryDirectory(prefix="hc-") as scratch:
        smoke(args, Path(scratch), screenshot)


if __name__ == "__main__":
    main()
