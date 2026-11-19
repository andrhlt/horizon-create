#!/usr/bin/env python3
"""Check the rendered Copycat Panel and Step appearance before and after material application."""

import argparse
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

reference = importlib.util.spec_from_file_location("render_fixture", ROOT / "tools/test-window-ctm.py")
render_fixture = importlib.util.module_from_spec(reference)
reference.loader.exec_module(render_fixture)

parser = argparse.ArgumentParser()
for name in ("ctl", "client", "resources"):
    parser.add_argument(name, type=Path)
parser.add_argument("--pack", type=Path)
parser.add_argument("--ffmpeg", default="ffmpeg")
args = parser.parse_args()

def inspect(control, y, z, path):
    control.command(f"/tp @s 8.5 171.4 26.8")
    control.call("look-at", 8.5, y, z)
    control.call("wait", 4)
    control.call("screenshot", path)
    pixels = render_fixture.image(args.ffmpeg, path, scaled=True)
    return sum(
        r > 120 and r > 1.45 * b and g > 1.35 * b
        for y in range(105, 206)
        for x in range(265, 375)
        for r, g, b in (render_fixture.rgb_at(pixels, x, y),)
    )

with TemporaryDirectory(prefix="copycat-frame-") as tmp, fixture_world(
    args, "CopycatRender", render=True, pack=args.pack,
) as ctl:
    ctl.command("/time set noon")
    ctl.call("key", "f1", "tap")
    for label, y, z in (("panel[facing=up]", 170.095, 23.5), ("step[facing=south,half=bottom]", 170.25, 23.75)):
        ctl.commands((
            "/setblock 8 170 23 air",
            f"/setblock 8 170 23 create:copycat_{label}",
            "/item replace entity @s hotbar.0 with minecraft:gold_block",
        ))
        ctl.call("select", "minecraft:gold_block")
        before = inspect(ctl, y, z, Path(tmp) / "before.png")
        ctl.command(f"/tp @s 10.5 169 {z}")
        ctl.call("look-at", 8.99, y, z)
        ctl.call("mouse", "right", "click")
        ctl.call("wait", 4)
        tag = ctl.command("/data get block 8 170 23 Material")
        after = inspect(ctl, y, z, Path(tmp) / "after.png")
        print(label, before, after, tag, flush=True)
        assert "minecraft:gold_block" in tag
        assert before == 0 and after > 2500, (label, before, after)
print("Both Copycat shapes rendered the placed material live.")
