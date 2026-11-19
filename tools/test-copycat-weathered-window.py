#!/usr/bin/env python3
"""Compare the Java Weathered Iron variants and tiles shown on painted Panels."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

weathered = import_module("test-weathered-window-ctm")
wrapped = import_module("test-copycat-wrapped-window")
Y, Z = wrapped.Y, wrapped.Z
PANEL = "create:copycat_panel[facing=north]"
OFFSETS = {"up": (0, 1), "down": (0, -1), "east": (1, 0), "west": (-1, 0)}


def run(args):
    with args.reference.open() as trace:
        rows = list(csv.DictReader(trace))
    failures = []
    with TemporaryDirectory(prefix="hc-cct-weathered-") as directory:
        scratch = Path(directory)
        pack = weathered.diagnostic_pack(args.pack or ROOT / ".local/create.hmod", scratch)
        frame = scratch / "frame.png"
        with fixture_world(args, "CopycatWeatheredWindow", render=True, pack=pack) as control:
            control.commands(("/time set noon", "/gamemode spectator"))
            control.call("key", "f1", "tap")
            previous = None
            for row in rows:
                x = int(row["x"])
                if previous is not None and previous != x:
                    control.command(weathered.window.block(previous, Y, Z))
                previous = x
                commands = [weathered.window.block(x + dx, Y + dy, Z) for dx, dy in OFFSETS.values()]
                commands.append(weathered.window.block(x, Y, Z, PANEL))
                if row["neighbor"] != "air":
                    dx, dy = OFFSETS[row["neighbor"]]
                    commands.append(weathered.window.block(x + dx, Y + dy, Z, weathered.BLOCK))
                control.commands(commands)
                wrapped.paint(control, x, Y, Z, weathered.BLOCK)
                face = row["face"]
                local = (.5, 1., .90) if face == "up" else (.5, .5, .5)
                weathered.view(control, (x, Y, Z), face, local)
                control.call("screenshot", frame)
                pixels = weathered.window.image(args.ffmpeg, frame, scaled=True)
                try:
                    observed = weathered.identify(pixels)
                except RuntimeError as error:
                    observed = str(error)
                expected = (int(row["variant"]), int(row["tile"]))
                if observed != expected:
                    failures.append((row, observed))
    for failure in failures:
        print(failure)
    if failures:
        raise RuntimeError(f"{len(failures)} of {len(rows)} Java Weathered Iron Copycat samples differed.")
    print(f"All {len(rows)} Java Weathered Iron Copycat tiles and cap variants matched Horizon's framebuffer.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for attribute in ("ctl", "client", "resources"):
        parser.add_argument(attribute, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/copycat-weathered-window-java.csv")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    run(parser.parse_args())
