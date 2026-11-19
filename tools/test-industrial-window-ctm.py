#!/usr/bin/env python3
"""Compare the rendered Industrial Iron rectangular window patterns with Java."""

import argparse
import csv
import importlib.util
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from fixture_world import ROOT, fixture_world

PALETTE = "industrial_iron_window"
FAMILY = "create:industrial_iron_window"
X, Y, Z = 8, 106, -10
LEVELS = (30, 85, 140, 195)
NORMAL = {"south": (0, 1), "west": (-1, 0), "north": (0, -1), "east": (1, 0)}


def load_helpers():
    script = ROOT / "tools/test-window-ctm.py"
    spec = importlib.util.spec_from_file_location("window_diagnostic", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


window = load_helpers()


def diagnostic_pack(pack, scratch):
    path = scratch / "industrial-diagnostic.hmod"
    with ZipFile(pack) as source, ZipFile(path, "w", ZIP_DEFLATED) as output:
        remaining = {
            window.tile_path(source, PALETTE, index): window.diagnostic_tile((250, LEVELS[index % 4], LEVELS[index // 4]))
            for index in range(16)
        }
        for item in source.infolist():
            payload = remaining.pop(item.filename, None)
            output.writestr(item, source.read(item) if payload is None else payload)
    if remaining:
        raise RuntimeError(f"Missing Industrial Iron CTM tiles: {sorted(remaining)}")
    return path


def verify_original_tiles(args, pack, scratch):
    reference = args.java_source / "src/main/resources/assets/create/textures/block/palettes/industrial_iron_window_connected.png"
    sheet = window.image(args.ffmpeg, reference)
    path = scratch / "extracted.png"
    with ZipFile(pack) as source:
        for tile_index in range(16):
            x, y = tile_index % 4 * 16, tile_index // 4 * 16
            expected = b"".join(sheet[4 * (64 * row + x):4 * (64 * row + x + 16)] for row in range(y, y + 16))
            path.write_bytes(source.read(window.tile_path(source, PALETTE, tile_index)))
            if window.image(args.ffmpeg, path) != expected:
                raise RuntimeError(f"Industrial Iron tile {tile_index} differs from the original RGBA.")


def prepare(control, pane, face, case, previous):
    nx, nz = NORMAL[face]
    rx, rz = -nz, nx

    def coords(height=0, across=0, depth=0):
        return X + across * rx + depth * nx, Y + height, Z + across * rz + depth * nz

    subject = FAMILY
    neighbor = FAMILY
    other = "create:ornate_iron_window"
    if pane:
        arms = "north=true,south=true" if nx else "east=true,west=true"
        subject += f"_pane[{arms}]"
        neighbor += "_pane[waterlogged=true]"
        other += "_pane"

    mask = case if case <= 15 else 15 if case == 16 else 8 if case == 19 else 1
    expected = {}
    for bit, offset in ((1, (1, 0, 0)), (2, (-1, 0, 0)), (4, (0, -1, 0)), (8, (0, 1, 0))):
        if mask & bit:
            expected[offset] = other if case == 20 else neighbor
    if case == 16:
        expected.update({(y, side, 0): neighbor for y in (-1, 1) for side in (-1, 1)})
    if case in (17, 18):
        expected[1, 0, 1] = neighbor if case == 17 else "minecraft:stone"
    if case == 19:
        expected[0, 1, 1] = neighbor
    placements = {coords(*offset): state for offset, state in expected.items()}
    commands = [window.block(*pos) for pos in sorted(previous.keys() - placements.keys())]
    commands.extend(window.block(*pos, state) for pos, state in placements.items() if previous.get(pos) != state)
    commands.append(window.block(*coords(), subject))
    control.commands(commands)
    control.call("tp", X + 0.5 + nx * 3.3, Y - 1, Z + 0.5 + nz * 3.3)
    control.call("look-at", X + 0.5, Y + 0.5, Z + 0.5)
    control.call("wait", 3)
    return placements


def read_index(pixels):
    red, green, blue = window.rgb_at(pixels, 319, 179)
    if red < 100:
        raise RuntimeError(f"The Industrial Iron center was not rendered: {(red, green, blue)}")
    cx, cy = (min(range(4), key=lambda i: abs(channel * 250 / red - LEVELS[i])) for channel in (green, blue))
    return cx + 4 * cy


def run(args, scratch):
    pack = args.pack or ROOT / ".local/create.hmod"
    if args.java_source:
        verify_original_tiles(args, pack, scratch)
    with (ROOT / "fixtures/industrial-window-ctm-java.csv").open() as source:
        cases = list(csv.DictReader(source))
    diagnostic = diagnostic_pack(pack, scratch)
    with fixture_world(args, "IndustrialWindowCTM", render=True, pack=diagnostic) as control:
        control.commands(("/time set noon", "/gamemode spectator"))
        control.call("key", "f1", "tap")
        previous = {}
        for row in cases:
            pane, face, case = row["pane"] == "true", row["face"], int(row["case"])
            previous = prepare(control, pane, face, case, previous)
            png = scratch / "frame.png"
            control.call("screenshot", png)
            rendered = read_index(window.image(args.ffmpeg, png, scaled=True))
            expected = int(row["tile"])
            print(f"Pane {pane}, {face} case {case}: Horizon {rendered}, Java {expected}", flush=True)
            if rendered != expected:
                raise RuntimeError("Industrial Iron rectangular CTM selection differs from Java.")
    print(f"Matched {len(cases)} Industrial Iron rendered Java tile selections.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--java-source", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    if not which(args.ffmpeg):
        parser.error("the Industrial Iron screenshot comparison requires ffmpeg")
    with TemporaryDirectory(prefix="hc-industrial-window-ctm-") as directory:
        run(args, Path(directory))


if __name__ == "__main__":
    main()
