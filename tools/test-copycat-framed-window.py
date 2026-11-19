#!/usr/bin/env python3
"""Compare framed glass and Industrial Iron texture tiles on Copycat Panels."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED

from fixture_world import ROOT, fixture_world
from window_ctm import WINDOW_TILE_DIRECTORY

window = import_module("test-window-ctm")
wrapped = import_module("test-copycat-wrapped-window")
framed = import_module("test-framed-glass-ctm")
X, Y, Z = wrapped.X, wrapped.Y, wrapped.Z
TILES = f"assets/create/textures/{WINDOW_TILE_DIRECTORY}"
FAMILIES = ("framed_glass", "horizontal_framed_glass", "vertical_framed_glass", "industrial_iron_window")
OFFSETS = {"up": (0, 1), "down": (0, -1), "west": (-1, 0), "east": (1, 0)}


def diagnostic_pack(source, scratch):
    output = scratch / "copycat-framed.hmod"
    plain = {
        "assets/create/textures/block/palettes/framed_glass.png",
        "assets/create/textures/block/palettes/industrial_iron_window.png",
    }
    tag = window.diagnostic_tile((245, 22, 245))
    with ZipFile(source) as archive, ZipFile(output, "w", compression=ZIP_DEFLATED) as patched:
        for entry in archive.infolist():
            path = Path(entry.filename.removeprefix(TILES + "/"))
            if entry.filename.startswith(TILES + "/") and path.parts[0] in FAMILIES and path.suffix == ".png":
                index = int(path.stem)
                color = (250, framed.LEVELS[index % 8], framed.LEVELS[index // 8])
                payload = window.diagnostic_tile(color, mirrored="mirrored" in path.parts)
            elif entry.filename in plain:
                payload = tag
            else:
                payload = archive.read(entry)
            patched.writestr(entry, payload)
    return output


def run(args):
    with args.reference.open() as trace:
        rows = list(csv.DictReader(trace))
    failures = []
    with TemporaryDirectory(prefix="hc-cct-framed-") as directory:
        scratch = Path(directory)
        pack = diagnostic_pack(args.pack or ROOT / ".local/create.hmod", scratch)
        frame = scratch / "frame.png"
        with fixture_world(args, "CopycatFramedWindow", render=True, pack=pack) as control:
            control.commands(("/time set noon", "/gamemode spectator"))
            control.call("key", "f1", "tap")
            for row in rows:
                face = row["face"]
                dx, dy = OFFSETS[row["toward"]]
                material = f"create:{row['family']}"
                subject = wrapped.facing("create:copycat_panel[facing=north]", face)
                neighbour = {"air": "minecraft:air", "glass": material, "painted-panel": subject}[row["neighbor"]]
                commands = [window.block(X + nx, Y + ny, Z) for nx, ny in OFFSETS.values()]
                commands.extend((
                    window.block(X, Y, Z, subject),
                    window.block(X + dx, Y + dy, Z, neighbour),
                ))
                control.commands(commands)
                wrapped.paint(control, X, Y, Z, material)
                if row["neighbor"] == "painted-panel":
                    wrapped.paint(control, X + dx, Y + dy, Z, material)
                control.call("tp", X + .5, Y - 1, Z + (3.8 if face == "south" else -2.8))
                control.call("look-at", X + .5, Y + .5, Z + .5)
                control.call("wait", 5)
                control.call("screenshot", frame)
                pixels = window.image(args.ffmpeg, frame, scaled=True)
                index = framed.grade(pixels, False, face)
                if index != int(row["tile"]):
                    failures.append((row, index, window.rgb_at(pixels, 319, 179)))
    for failure in failures:
        print(failure)
    if failures:
        raise RuntimeError(f"{len(failures)} of {len(rows)} Java framed window Copycat faces differed.")
    print(f"All {len(rows)} Java framed glass and Industrial Iron Copycat faces matched Horizon's framebuffer.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for attribute in ("ctl", "client", "resources"):
        parser.add_argument(attribute, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/copycat-framed-window-java.csv")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    run(parser.parse_args())
