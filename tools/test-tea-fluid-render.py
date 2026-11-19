#!/usr/bin/env python3
"""Check that the Basin renders the original warm tea sprite instead of water."""
import argparse
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

BASIN = "5 97 -9"


def center_color(path):
    filters = "crop=12:12:(iw-12)/2:(ih-12)/2,scale=1:1"
    pixels = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", path, "-vf", filters,
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ])
    return tuple(pixels)


def run(args, scratch):
    env = {"HORIZON_NO_AUDIO": "1"}
    with fixture_world(args, "TeaFluidRender", render=True, pack=args.pack, env=env) as world:
        world.commands((
            "/time set noon",
            "/fill 3 96 -11 8 96 -6 minecraft:smooth_stone",
            f"/setblock {BASIN} create:basin",
            "/tp @s 5.5 100 -8.5",
        ))
        world.call("key", "f1", "tap")
        world.call("look-at", 5.5, 97.25, -8.5)
        colors = []
        for fluid in ("minecraft:water", "create:tea"):
            world.command(f'/data merge block {BASIN} {{OutputTanks:[{{TankContent:{{Fluid:{{id:"{fluid}",amount:900}}}}}}]}}')
            tick = world.clock()
            for n in range(1, 9):
                world.step_to(tick + n)
            world.call("wait", 4)
            frame = scratch / f"{fluid.split(':')[1]}.png"
            world.call("screenshot", frame)
            colors.append(center_color(frame))
        water, tea = colors
        assert water[2] > water[0] and tea[0] > tea[1] > tea[2], colors
        print(f"Basin water center RGB {water} and tea center RGB {tea}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="hc-tea-render-") as directory:
        scratch = args.screenshots or Path(directory)
        scratch.mkdir(parents=True, exist_ok=True)
        run(args, scratch)
