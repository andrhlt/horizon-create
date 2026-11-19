#!/usr/bin/env python3
"""Compare stock Horizon CTM tile selection with actual Java window contexts."""

import argparse
import csv
from pathlib import Path
from shutil import which
import struct
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile
import zlib

from fixture_world import ROOT, fixture_world
from window_ctm import JAVA_TILE_ORDER, PNG, WINDOW_TILE_DIRECTORY, VERTICAL_WINDOWS, png_chunk

COLORS = ((250, 25, 25), (25, 250, 25), (25, 25, 250), (240, 240, 40))
X, Y, Z = 8, 106, -10


def diagnostic_tile(rgb, *, mirrored=False):
    line = bytearray(b"\0")
    for column in range(16):
        u = 15 - column if mirrored else column
        brightness = 0.55 if u < 7 else 1.0 if u < 9 else 0.80
        line.extend(int(channel * brightness) for channel in rgb)
        line.append(255)
    ihdr = struct.pack(">IIBBBBB", 16, 16, 8, 6, 0, 0, 0)
    return PNG + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", zlib.compress(line * 16)) + png_chunk(b"IEND", b"")


def tile_path(archive, family, tile):
    path = f"assets/create/textures/{WINDOW_TILE_DIRECTORY}/{family}/{tile}.png"
    try:
        return archive.getinfo(path).filename
    except KeyError:
        # Earlier immutable candidates used OptiFine's own tile directory.
        return f"assets/create/optifine/ctm/{family}/{tile}.png"


def diagnostic_pack(pack, scratch):
    path = scratch / "diagnostic.hmod"
    with ZipFile(pack) as original, ZipFile(path, "w", compression=ZIP_DEFLATED) as output:
        replace = {
            tile_path(original, f"{family}_window", tile): diagnostic_tile(COLORS[java])
            for family in VERTICAL_WINDOWS for tile, java in enumerate(JAVA_TILE_ORDER)
        }
        for item in original.infolist():
            payload = replace.pop(item.filename, None)
            output.writestr(item, original.read(item) if payload is None else payload)
        if replace:
            raise RuntimeError(f"Pack is missing Create's connected window tiles: {sorted(replace)}")
    return path

def image(ffmpeg, source, scaled=False):
    filters = ["-vf", "scale=640:360"] if scaled else []
    return subprocess.check_output([
        ffmpeg, "-v", "error", "-threads", "1", "-filter_threads", "1", "-i", str(source),
        *filters, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "pipe:1",
    ])


def verify_original_tiles(args, pack, scratch):
    source_textures = args.java_source / "src/main/resources/assets/create/textures/block/palettes"
    with ZipFile(pack) as archive:
        for family in VERTICAL_WINDOWS:
            name = f"{family}_window"
            source = image(args.ffmpeg, source_textures / f"{name}_connected.png")
            for tile, java in enumerate(JAVA_TILE_ORDER):
                x, y = java % 2 * 16, java // 2 * 16
                expected = b"".join(source[4 * (32 * row + x):4 * (32 * row + x + 16)] for row in range(y, y + 16))
                local = scratch / "tile.png"
                local.write_bytes(archive.read(tile_path(archive, name, tile)))
                if image(args.ffmpeg, local) != expected:
                    raise RuntimeError(f"Pack changed the Java {name} CTM pixels for index {java}.")


def block(x, y, z, state="minecraft:air"):
    return f"/setblock {x} {y} {z} {state}"


def prepare_case(control, family, pane, case):
    suffix = "_window_pane" if pane else "_window"
    own = f"create:{family}{suffix}"
    other = "oak" if family == "acacia" else "acacia"
    subject = own + ("[east=true,west=true]" if pane else "")
    matching = own + ("[waterlogged=true]" if pane else "")
    commands = [block(X, Y + dy, z) for z in (Z, Z + 1) for dy in (-1, 1)]
    commands.append(block(X, Y, Z, subject))
    if case in (1, 3, 4, 5, 7):
        commands.append(block(X, Y + 1, Z, matching))
    if case in (2, 3, 7):
        commands.append(block(X, Y - 1, Z, matching))
    if case == 4:
        commands.append(block(X, Y + 1, Z + 1, matching))
    if case == 5:
        commands.append(block(X, Y + 1, Z + 1, "minecraft:stone"))
    if case == 6:
        commands.append(block(X, Y + 1, Z, f"create:{other}{suffix}"))
    control.commands(commands)
    control.call("tp", X + 0.5, Y - 1, Z - 2.8 if case == 7 else Z + 3.8)
    control.call("look-at", X + 0.5, Y + 0.5, Z + 0.5)
    control.call("wait", 5)


def rgb_at(pixels, x, y):
    offset = 4 * (640 * y + x)
    return tuple(pixels[offset:offset + 3])


def check_frame(pixels, case, java, label, pane):
    red, green, blue = center = rgb_at(pixels, 319, 179)
    rendered = 3 if red > 1.8 * blue and green > 1.8 * blue else center.index(max(center))
    if max(center) < 100 or rendered != java:
        raise RuntimeError(f"{label}: expected Java tile {java}; Horizon drew {center}.")
    if case in (3, 7):
        # The pane's partial/mirrored quads leave upper/lower CT unchanged.
        # Their U still uses a dim left band, brightest central post, and
        # medium right band. The pane mirrors its U on the opposite face.
        left, right = (max(rgb_at(pixels, x, 179)) / max(center) for x in (300, 340))
        if case == 7 and pane:
            left, right = right, left
        if not (0.47 < left < 0.64 and 0.71 < right < 0.90):
            raise RuntimeError(f"{label}: Horizon changed the original model U slices: {left:.2f}, {right:.2f}.")


def run(args, scratch):
    pack = args.pack or ROOT / ".local/create.hmod"
    reference = ROOT / "fixtures/window-ctm-java.csv"
    with reference.open() as source:
        cases = list(csv.DictReader(source))
    if args.java_source:
        verify_original_tiles(args, pack, scratch)
    diagnostic = diagnostic_pack(pack, scratch)
    output = ROOT / ".local/window-ctm"
    output.mkdir(exist_ok=True)
    with fixture_world(args, "WindowCTM", render=True, pack=diagnostic) as control:
        control.commands(("/time set noon", "/gamemode spectator"))
        control.call("key", "f1", "tap")
        for row in cases:
            family = row["family"]
            pane = row["pane"] == "true"
            case = int(row["case"])
            label = f"{family}{'_pane' if pane else ''}-{case}"
            prepare_case(control, family, pane, case)
            frame = output / f"{label}.png" if case in (3, 4, 7) and family in ("oak", "ornate_iron") else scratch / "frame.png"
            control.call("screenshot", frame)
            check_frame(image(args.ffmpeg, frame, scaled=True), case, int(row["tile"]), label, pane)
    print(f"Matched {len(cases)} rendered Java CTM tile selections, including front blockers and mirrored pane UVs.")
    if args.java_source:
        print("Matched all 48 original Java CTM tiles pixel for pixel, including alpha.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--java-source", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    if not which(args.ffmpeg):
        parser.error("the window CTM screenshot comparison requires ffmpeg")
    with TemporaryDirectory(prefix="hc-window-ctm-") as directory:
        run(args, Path(directory))


if __name__ == "__main__":
    main()
