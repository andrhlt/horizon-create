#!/usr/bin/env python3
"""Replay Java's framed-glass contexts on Horizon's rendered block and pane models."""

import argparse
import csv
import importlib.util
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from fixture_world import ROOT, fixture_world
from framed_glass_ctm import SIDES

ORIGIN = (8, 106, -10)
NORMAL = {"down": (0, -1, 0), "up": (0, 1, 0), "north": (0, 0, -1),
          "south": (0, 0, 1), "west": (-1, 0, 0), "east": (1, 0, 0)}
STEPS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))
LEVELS = (16, 43, 70, 97, 124, 151, 178, 205)


def load_helpers():
    script = ROOT / "tools/test-window-ctm.py"
    spec = importlib.util.spec_from_file_location("window_diagnostic", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


window = load_helpers()


def entries(archive):
    for name, (method, indices, _) in SIDES.items():
        grid = 8 if method == "ctm" else 2
        for index in sorted(set(indices)):
            for mirrored in (False, True):
                stem = f"mirrored/{index}" if mirrored else str(index)
                yield name, grid, index, mirrored, window.tile_path(archive, name, stem)


def diagnostic_pack(pack, scratch):
    path = scratch / "framed-diagnostic.hmod"
    with ZipFile(pack) as source, ZipFile(path, "w", ZIP_DEFLATED) as output:
        remaining = {
            path: window.diagnostic_tile((250, LEVELS[index % 8], LEVELS[index // 8]), mirrored=mirrored)
            for _, _, index, mirrored, path in entries(source)
        }
        for item in source.infolist():
            payload = remaining.pop(item.filename, None)
            output.writestr(item, source.read(item) if payload is None else payload)
    if remaining:
        raise RuntimeError(f"Missing framed-glass CTM tiles: {sorted(remaining)}")
    return path


def verify_original_tiles(args, pack, scratch):
    textures = args.java_source / "src/main/resources/assets/create/textures/block/palettes"
    originals = {name: window.image(args.ffmpeg, textures / f"{name}_connected.png") for name in SIDES}
    local = scratch / "extracted.png"
    with ZipFile(pack) as source:
        for name, grid, index, mirrored, path in entries(source):
            sheet = originals[name]
            x, y = index % grid * 16, index // grid * 16
            columns = range(x + 15, x - 1, -1) if mirrored else range(x, x + 16)
            expected = b"".join(
                sheet[4*(16*grid*row + col):4*(16*grid*row + col + 1)]
                for row in range(y, y + 16) for col in columns
            )
            local.write_bytes(source.read(path))
            if window.image(args.ffmpeg, local) != expected:
                raise RuntimeError(f"Original framed-glass RGBA pixels differ for {path}.")


def prepare(control, name, pane, face, mask, previous):
    nx, ny, nz = NORMAL[face]
    right = (1, 0, 0) if ny else (nz, 0, -nx)
    up = (0, 0, -ny) if ny else (0, 1, 0)
    subject = neighbor = f"create:{name}"
    if pane:
        arms = "north=true,south=true" if nx else "east=true,west=true"
        subject += f"_pane[{arms}]"
        neighbor += "_pane[waterlogged=true]"
    desired = {
        tuple(origin + row * vertical + col * across
              for origin, vertical, across in zip(ORIGIN, up, right, strict=True)): neighbor
        for i, (row, col) in enumerate(STEPS) if mask & (1 << i)
    }
    commands = [window.block(*pos) for pos in sorted(previous.keys() - desired.keys())]
    commands.extend(window.block(*pos, state) for pos, state in desired.items() if previous.get(pos) != state)
    commands.append(window.block(*ORIGIN, subject))
    control.commands(commands)
    x, y, z = (coord + 0.5 for coord in ORIGIN)
    control.call("tp", x + nx * 3.3, y + ny * 3.3 - 1.62, z + nz * 3.3)
    control.call("look-at", x, y, z)
    control.call("wait", 3)
    return desired


def grade(pixels, pane, face):
    red, green, blue = window.rgb_at(pixels, 319, 179)
    marker = red >= 100 and red > 1.11 * max(green, blue)
    if not marker:
        return -1
    index_x, index_y = (
        min(range(8), key=lambda i: abs(channel * 250 / red - LEVELS[i]))
        for channel in (green, blue)
    )
    if pane:
        left, right = (window.rgb_at(pixels, x, 179)[0] / red for x in (300, 340))
        if face in ("north", "west"):
            left, right = right, left
        if not (0.47 < left < 0.64 and 0.71 < right < 0.90):
            raise RuntimeError(f"Framed pane did not preserve Java's U slices: {left:.2f}, {right:.2f}.")
    return index_x + 8 * index_y


def run(args, scratch):
    if args.java_source:
        verify_original_tiles(args, args.pack, scratch)
    with (ROOT / "fixtures/framed-glass-ctm-java.csv").open() as source:
        cases = list(csv.DictReader(source))
    pack = diagnostic_pack(args.pack, scratch)
    with fixture_world(args, "FramedGlassCTM", render=True, pack=pack) as control:
        control.commands(("/time set noon", "/gamemode spectator"))
        control.call("key", "f1", "tap")
        previous = {}
        for row in cases:
            name, pane, face = row["family"], row["pane"] == "true", row["face"]
            mask, expected = int(row["mask"]), int(row["tile"])
            previous = prepare(control, name, pane, face, mask, previous)
            frame = scratch / "frame.png"
            control.call("screenshot", frame)
            rendered = grade(window.image(args.ffmpeg, frame, scaled=True), pane, face)
            line = f"{name}, pane {pane}, {face}, mask {mask}: Horizon {rendered}, Java {expected}"
            print(line, flush=True)
            if rendered != expected:
                raise RuntimeError(line)

    print(f"Matched {len(cases)} framed-glass render contexts.")
    if args.java_source:
        print("Matched all 110 original or mirrored framed-glass CTM tiles, including alpha.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--java-source", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    if not which(args.ffmpeg):
        parser.error("the framed-glass screenshot comparison requires ffmpeg")
    with TemporaryDirectory(prefix="hc-framed-glass-ctm-") as directory:
        run(args, Path(directory))


if __name__ == "__main__":
    main()
