#!/usr/bin/env python3
"""Compare the rendered Train Signal lamp in the dark with a frozen world."""

import argparse
import csv
from pathlib import Path
from struct import unpack
from subprocess import check_output
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

SIGNAL = "8 96 40"
PERIOD = 40


def peak_red(image, ffmpeg):
    width, height = unpack(">II", image.read_bytes()[16:24])
    crop = f"crop={width // 5}:{height // 5}:{2 * width // 5}:{2 * height // 5}"
    raw = check_output([str(ffmpeg), "-v", "error", "-i", str(image), "-vf", crop,
                        "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
    return max((r for r, g, b in zip(raw[::3], raw[1::3], raw[2::3], strict=True)
                if r >= 2 * max(g, b)), default=0)


def run(args):
    with (ROOT / "fixtures/train-signal-lamp-java.csv").open() as reference:
        lit_by_phase = {int(row["phase"]): row["red"] == "true" for row in csv.DictReader(reference)}
    if set(lit_by_phase) != set(range(PERIOD)):
        raise RuntimeError("The captured Java sample must include every lamp phase.")

    with fixture_world(args, "train-signal-lamp", render=True, pack=args.pack) as control, TemporaryDirectory(
        prefix="hc-signal-lamp-"
    ) as scratch:
        scratch = Path(scratch)
        control.commands((
            "/fill 5 95 37 11 100 45 minecraft:smooth_stone hollow",
            "/tp @s 8.5 96 43.3 180 21",
            "/gamemode survival",
        ))
        for _ in range(5):
            control.step_to(control.clock() + 1)
        control.call("look-at", 8.5, 96.625, 40.5)
        control.call("wait", 8)
        control.call("key", "f1", "tap")
        control.command(f'/setblock {SIGNAL} create:track_signal{{State:"RED",Overlay:"SKIP"}}')

        for name in ("red", "green"):
            if name == "green":
                control.command(f'/data merge block {SIGNAL} {{State:"GREEN"}}')
            control.call("wait", 5)
            image = ROOT / f".local/train-signal-lamp-{name}.png"
            control.call("screenshot", image)
            peak = peak_red(image, args.ffmpeg)
            if (peak >= 150) != (name == "red"):
                raise RuntimeError(f"The dark-room {name} lamp did not match Java (peak red {peak}).")

        control.command(f'/data merge block {SIGNAL} {{State:"INVALID"}}')
        control.call("wait", 5)
        world_tick = control.clock()
        sampled = set()
        for sweep in range(3):
            images = [scratch / f"lamp-{sweep}-{index}.png" for index in range(110)]
            observations = control.call("script", script="".join(
                f"state\nscreenshot {image}\nstate\n" for image in images
            ))
            ticks = [result["ticks"] for result in observations if "player" in result]
            for image, (before, after) in zip(images, zip(ticks[::2], ticks[1::2], strict=True), strict=True):
                phase = before % PERIOD
                if before != after or phase in sampled:
                    continue
                actual = peak_red(image, args.ffmpeg) >= 150
                if actual != lit_by_phase[phase]:
                    raise RuntimeError(f"Lamp on client tick {before} was {actual}, "
                                       f"Java expected {lit_by_phase[phase]}.")
                sampled.add(phase)
            if len(sampled) == PERIOD:
                break
        if len(sampled) != PERIOD:
            raise RuntimeError(f"Missing same-tick lamp frames at {sorted(set(lit_by_phase) - sampled)}.")
        if control.clock() != world_tick:
            raise RuntimeError("The game clock advanced in the frozen-world lamp fixture.")
    print(f"Dark-room red and ambient lamps matched Java. {len(sampled)} blink phases matched with game time frozen.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    run(parser.parse_args())
