#!/usr/bin/env python3
"""Compare rendered Horizon Copper Casing quads with a hidden Java Create client."""

import argparse
import csv
import importlib
import json
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from copper_casing_ctm import BASE, OMNI, TILES
from fixture_world import ROOT, fixture_world

window = importlib.import_module("test-window-ctm")
weathered = importlib.import_module("test-weathered-window-ctm")

ARTWORK = "assets/create/textures/block"
ASSETS = "assets/create/textures"
INDICES = sorted(set(OMNI))
MARKERS = {str(tile): (250, 35 + 24 * (tile % 8), 35 + 24 * (tile // 8)) for tile in INDICES}
MARKERS.update({"open": (250, 6, 7), "unshifted": (250, 231, 11)})
POS = (8, 196, 8)


def tile_name(tile):
    return f"{ASSETS}/{TILES}/{tile}.png"


def verify_artwork(pack, java, ffmpeg, scratch):
    java = java / "src/main/resources" / ARTWORK
    sheet = window.image(ffmpeg, java / "copper_casing_connected.png")
    png = scratch / "tile.png"
    with ZipFile(pack) as archive:
        for tile in INDICES:
            x, y = 16 * (tile % 8), 16 * (tile // 8)
            expected = b"".join(sheet[4 * (128 * row + x):4 * (128 * row + x + 16)]
                                for row in range(y, y + 16))
            png.write_bytes(archive.read(tile_name(tile)))
            if window.image(ffmpeg, png) != expected:
                raise RuntimeError(f"Copper Casing Java tile {tile} differs.")
        for name, file in ((tile_name("base"), "copper_casing.png"),
                           (f"{ARTWORK}/encased_pipe.png", "encased_pipe.png")):
            if archive.read(name) != (java / file).read_bytes():
                raise RuntimeError(f"Copper Casing Java sprite {file} differs.")
        for model, key, sprite in (
                ("copper_casing", "all", BASE),
                ("encased_fluid_pipe/block_flat", "0", BASE),
                ("encased_fluid_pipe/block_open", "0", "create:block/encased_pipe")):
            data = json.loads(archive.read(f"assets/create/models/block/{model}.json"))
            if data["textures"][key] != sprite:
                raise RuntimeError(f"Copper Casing sprite incorrectly selected in {model}.")
    print(f"Matched all {len(INDICES)} Java Copper Casing tiles, their base sprite and the open port sprite.")


def diagnostic_pack(pack, scratch):
    target = scratch / "copper-casing-diagnostic.hmod"
    replacements = {tile_name(tile): window.diagnostic_tile(MARKERS[str(tile)]) for tile in INDICES}
    replacements[tile_name("base")] = window.diagnostic_tile(MARKERS["unshifted"])
    replacements[f"{ARTWORK}/encased_pipe.png"] = window.diagnostic_tile(MARKERS["open"])
    with ZipFile(pack) as source, ZipFile(target, "w", ZIP_DEFLATED) as output:
        for entry in source.infolist():
            replacement = replacements.pop(entry.filename, None)
            output.writestr(entry, source.read(entry) if replacement is None else replacement)
    if replacements:
        raise RuntimeError(f"Missing diagnostic surfaces: {list(replacements)}")
    return target


def place(control, layout, previous):
    ready = {}
    for piece in layout.split("|"):
        coords, state = piece.split("=", 1)
        position = tuple(base + int(delta) for base, delta in zip(POS, coords.split(":"), strict=True))
        ready[position] = state
    commands = [window.block(*pos) for pos in sorted(previous.keys() - ready.keys())]
    commands.extend(window.block(*pos, state) for pos, state in ready.items() if previous.get(pos) != state)
    if commands:
        control.commands(commands)
    return ready


def identify(pixels):
    red, green, blue = window.rgb_at(pixels, 319, 179)
    if red < 34 or red < max(green, blue):
        return None, (red, green, blue)
    ratios = (250 * green / red, 250 * blue / red)
    distances = {
        key: sum((actual - expected) ** 2 for actual, expected in zip(ratios, marker[1:], strict=True))
        for key, marker in MARKERS.items()
    }
    best = min(distances, key=distances.get)
    return best if distances[best] < 9 ** 2 else None, (red, green, blue)


def run(args, scratch):
    if args.java_source:
        verify_artwork(args.pack, args.java_source, args.ffmpeg, scratch)
    pack = diagnostic_pack(args.pack, scratch)
    with args.fixture.open() as source:
        rows = list(csv.DictReader(source))
    with fixture_world(args, "CopperCasingCTM", render=True, pack=pack, env={"HORIZON_NO_AUDIO": "1"}) as control:
        control.commands(("/time set noon", "/gamemode spectator"))
        control.call("key", "f1", "tap")
        weathered.view(control, POS, rows[0]["face"], (.5, .5, .5))
        control.call("wait-ready")
        previous = {}
        failure = []
        for row in rows:
            previous = place(control, row["layout"], previous)
            weathered.view(control, POS, row["face"], (.5, .5, .5))
            frame = scratch / "frame.png"
            control.call("screenshot", frame)
            pixels = window.image(args.ffmpeg, frame, scaled=True)
            actual, color = identify(pixels)
            label = f"{row['face']}/{row['case']}"
            print(f"{label}: Horizon {actual} {color}, Java {row['tile']}", flush=True)
            if actual != row["tile"]:
                failure.append(label)
    if failure:
        raise RuntimeError(f"{len(failure)} Copper Casing quads differ: {', '.join(failure)}")
    print(f"Matched all {len(rows)} rendered Copper Casing and Encased Pipe faces against Java.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--java-source", type=Path)
    parser.add_argument("--fixture", type=Path, default=ROOT / "fixtures/copper-casing-ctm-java.csv")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    if not which(args.ffmpeg):
        parser.error("the Copper Casing visual replay requires ffmpeg")
    with TemporaryDirectory(prefix="hc-copper-casing-ctm-") as directory:
        run(args, Path(directory))


if __name__ == "__main__":
    main()
