#!/usr/bin/env python3
"""Compare Java's selected textures on painted Copycat Panels and Steps."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED

from fixture_world import ROOT, fixture_world

window = import_module("test-window-ctm")
joins = import_module("test-copycat-window-joins")
X, Y, Z = joins.X, joins.Y, joins.Z
OAK = "create:oak_window"
RAW_TILE = "assets/create/textures/block/palettes/oak_window.png"


def diagnostic_pack(source, scratch):
    base = window.diagnostic_pack(source, scratch)
    output = scratch / "copied-windows.hmod"
    sentinel = window.diagnostic_tile((245, 22, 245))
    with ZipFile(base) as original, ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for entry in original.infolist():
            archive.writestr(entry, sentinel if entry.filename == RAW_TILE else original.read(entry))
    return output


def facing(state, face):
    if face != "north" or "facing=" not in state:
        return state
    original = "north" if "facing=north" in state else "south"
    flipped = "south" if original == "north" else "north"
    return state.replace(f"facing={original}", f"facing={flipped}")


def paint(control, x, y, z, material):
    nbt = '{Material:{Name:"%s"},Item:{id:"%s",count:1}}' % (material, material)
    control.command(f"/data merge block {x} {y} {z} {nbt}")


def step_arrangement(row):
    half = row["subject"]
    opposite = "bottom" if half == "top" else "top"
    subject = f"create:copycat_step[facing=north,half={half}]"
    neighbour, material = {
        "air": ("minecraft:air", None),
        "oak": (OAK, None),
        "oak-panel": ("create:copycat_panel[facing=north]", OAK),
        "like-step": (subject, OAK),
        "other-half": (f"create:copycat_step[facing=north,half={opposite}]", OAK),
        "other-facing": (f"create:copycat_step[facing=south,half={opposite}]", OAK),
        "birch-step": (f"create:copycat_step[facing=north,half={opposite}]", "create:birch_window"),
    }[row["neighbor"]]
    return subject, neighbour, material, .75 if half == "top" else .25


def panel_arrangement(row):
    direction = "south" if row["subject"] == "panel-inward" else "north"
    subject = f"create:copycat_panel[facing={direction}]"
    neighbour, material = joins.CASES[row["neighbor"]]
    return subject, neighbour, material, .5


def run(args):
    with args.reference.open() as trace:
        rows = list(csv.DictReader(trace))
    failures = []
    arrangement = step_arrangement if args.steps else panel_arrangement
    with TemporaryDirectory(prefix="hc-cct-panel-") as directory:
        scratch = Path(directory)
        pack = diagnostic_pack(args.pack or ROOT / ".local/create.hmod", scratch)
        with fixture_world(args, "CopycatWrappedWindow", render=True, pack=pack) as control:
            control.commands(("/time set noon", "/gamemode spectator"))
            control.call("key", "f1", "tap")
            for row in rows:
                face = row["face"]
                dy = 1 if row["toward"] == "up" else -1
                subject, neighbour, material, sample_height = arrangement(row)
                control.commands((
                    window.block(X, Y + 1, Z), window.block(X, Y - 1, Z),
                    window.block(X, Y, Z, facing(subject, face)),
                    window.block(X, Y + dy, Z, facing(neighbour, face)),
                ))
                paint(control, X, Y, Z, OAK)
                if material:
                    paint(control, X, Y + dy, Z, material)
                control.call("tp", X + .5, Y - 1, Z + (3.8 if face == "south" else -2.8))
                control.call("look-at", X + .5, Y + sample_height, Z + .5)
                control.call("wait", 5)
                frame = scratch / "frame.png"
                control.call("screenshot", frame)
                label = (row["subject"], row["neighbor"], row["toward"], face)
                pixels = window.image(args.ffmpeg, frame, scaled=True)
                red, green, blue = window.rgb_at(pixels, 319, 179)
                if red > green * 2 and blue > green * 2:
                    failures.append(f"{label}: drew the plain sprite instead of Java connected tile {row['tile']}")
                    continue
                dim, middle, bright = sorted((red, green, blue))
                if bright < 2 * middle and (row["tile"] != "3" or middle <= 2 * dim):
                    failures.append(f"{label}: no diagnostic window tile at the sampled pixel, {(red, green, blue)}")
                    continue
                try:
                    window.check_frame(pixels, 0, int(row["tile"]), label, False)
                except RuntimeError as error:
                    failures.append(str(error))
    for failure in failures:
        print(failure)
    shape = "Step" if args.steps else "Panel"
    if failures:
        raise RuntimeError(f"{len(failures)} of {len(rows)} Java painted {shape} faces differed.")
    print(f"All {len(rows)} Java painted {shape} faces matched Horizon's framebuffer.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for attribute in ("ctl", "client", "resources"):
        parser.add_argument(attribute, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--steps", action="store_true")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    if args.reference is None:
        filename = "copycat-step-window-java.csv" if args.steps else "copycat-wrapped-window-java.csv"
        args.reference = ROOT / "fixtures" / filename
    run(args)
