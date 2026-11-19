#!/usr/bin/env python3
"""Replay Java's Weathered Iron atlas and rectangle choices on rendered Horizon quads."""

import argparse
import csv
import importlib.util
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from fixture_world import ROOT, fixture_world

BLOCK = "create:weathered_iron_window"
PALETTE = "weathered_iron_window"
TEXTURES = "assets/create/textures/block/palettes"
VARIANTS = (28, 82, 148, 207)
TILES = tuple(17 + 13 * index for index in range(16))
NORMALS = {"up": (0, 1, 0), "down": (0, -1, 0), "north": (0, 0, -1), "south": (0, 0, 1),
           "west": (-1, 0, 0), "east": (1, 0, 0)}
ARMS = (
    None, "", "east=true,west=true", "north=true,south=true", "north=true,east=true",
    "north=true,east=true,south=true,west=true",
)
NEIGHBORS = {1: (0, 1, 0), 4: (1, 0, 0), 16: (0, -1, 0), 64: (-1, 0, 0)}


def load_visual_helpers():
    path = ROOT / "tools/test-window-ctm.py"
    spec = importlib.util.spec_from_file_location("window_diagnostic", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


window = load_visual_helpers()


def verify_tiles(pack, java, ffmpeg, scratch):
    source = java / "src/main/resources" / TEXTURES
    local = scratch / "tile.png"
    with ZipFile(pack) as archive:
        for variant in range(4):
            sheet = window.image(ffmpeg, source / f"weathered_iron_window_{variant+1}_connected.png")
            for index in range(16):
                x, y = index % 4 * 16, index // 4 * 16
                expected = b"".join(sheet[4 * (64 * row + x):4 * (64 * row + x + 16)]
                                    for row in range(y, y + 16))
                local.write_bytes(archive.read(window.tile_path(archive, PALETTE, f"{variant}/{index}")))
                if window.image(ffmpeg, local) != expected:
                    raise RuntimeError(f"The original Weathered Iron tile differs for atlas {variant}, tile {index}.")


def diagnostic_pack(pack, scratch):
    target = scratch / "weathered-diagnostic.hmod"
    with ZipFile(pack) as source, ZipFile(target, "w", ZIP_DEFLATED) as output:
        replacements = {
            window.tile_path(source, PALETTE, f"{variant}/{tile}"):
                window.diagnostic_tile((250, VARIANTS[variant], TILES[tile]))
            for variant in range(4) for tile in range(16)
        }
        replacements.update({
            f"{TEXTURES}/weathered_iron_window_{v+1}_end.png": window.diagnostic_tile((250, hue, 0))
            for v, hue in enumerate(VARIANTS)
        })
        for item in source.infolist():
            data = replacements.pop(item.filename, None)
            output.writestr(item, source.read(item) if data is None else data)
    if replacements:
        raise RuntimeError(f"Missing Weathered Iron artwork in the pack: {sorted(replacements)}")
    return target


def setup_scene(control, pos, shape, mask, previous):
    name = BLOCK if shape == 0 else f"{BLOCK}_pane"
    arms = ARMS[shape]
    center = f"{name}[{arms}]" if arms else name
    desired = {
        tuple(a+b for a, b in zip(pos, offset, strict=True)): name
        for bit, offset in NEIGHBORS.items() if mask & bit
    }
    actions = [window.block(*old) for old in sorted(previous.keys() - desired.keys() - {pos})]
    actions.extend(window.block(*at, block) for at, block in desired.items() if previous.get(at) != block)
    actions.append(window.block(*pos, center))
    control.commands(actions)
    desired[pos] = center
    return desired


def view(control, pos, face, offset):
    target = tuple(a + b for a, b in zip(pos, offset, strict=True))
    camera = tuple(
        center + delta * 3.3 - eye
        for center, delta, eye in zip(target, NORMALS[face], (0, 1.62, 0), strict=True)
    )
    control.call("tp", *camera)
    control.call("look-at", *target)
    control.call("wait", 3)


def identify(pixels):
    red, green, blue = window.rgb_at(pixels, 319, 179)
    if red < 70 or red < 1.12 * max(green, blue):
        raise RuntimeError(f"The colored Weathered Iron quad was not visible: {(red, green, blue)}")
    variant = min(range(4), key=lambda i: abs(VARIANTS[i] - 250 * green / red))
    tile = -1 if blue <= 3 else min(range(16), key=lambda i: abs(TILES[i] - 250 * blue / red))
    return variant, tile


def run(args, scratch):
    if args.java_source:
        verify_tiles(args.pack, args.java_source, args.ffmpeg, scratch)
    pack = diagnostic_pack(args.pack, scratch)
    with (ROOT / "fixtures/weathered-window-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    with fixture_world(args, "WeatheredWindowCTM", render=True, pack=pack) as control:
        control.commands(("/time set noon", "/gamemode spectator"))
        control.call("key", "f1", "tap")
        previous = {}
        current = None
        for row in rows:
            pos = tuple(int(row[key]) for key in ("x", "y", "z"))
            shape, mask = (int(row[key]) for key in ("shape", "mask"))
            context = (pos, shape, mask)
            offset = tuple(float(row[key]) for key in ("local_x", "local_y", "local_z"))
            face = row["facing"]
            if current != context:
                if current is None or pos != current[0]:
                    view(control, pos, face, offset)
                    control.call("wait-ready")
                previous = setup_scene(control, pos, shape, mask, previous)
                current = context
            view(control, pos, face, offset)
            frame = scratch / "frame.png"
            control.call("screenshot", frame)
            pixels = window.image(args.ffmpeg, frame, scaled=True)
            actual = identify(pixels)
            expected = (int(row["variant"]), int(row["tile"]))
            description = f"Weathered {pos}, shape {shape}, mask {mask}, face {face}, quad {row['quad']}"
            print(f"{description}: Horizon {actual}, Java {expected}", flush=True)
            if actual != expected:
                raise RuntimeError(description)
    print(f"Matched all {len(rows)} rendered Weathered Iron quads against Java.")
    if args.java_source:
        print("Matched all 64 original Java tiles pixel for pixel, including alpha.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--java-source", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    if not which(args.ffmpeg):
        parser.error("the Weathered Iron visual replay requires ffmpeg")
    with TemporaryDirectory(prefix="hc-weathered-window-ctm-") as directory:
        run(args, Path(directory))


if __name__ == "__main__":
    main()
