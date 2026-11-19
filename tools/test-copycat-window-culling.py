#!/usr/bin/env python3
"""Verify Java's shared-face visibility with a real painted Copycat neighbour."""
import argparse
import csv
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from fixture_world import ROOT, fixture_world

window = import_module("test-window-ctm")
wrapped = import_module("test-copycat-wrapped-window")
X, Y, Z = wrapped.X, wrapped.Y, wrapped.Z
COLORS = ((245, 22, 230), (26, 245, 230))


def diagnostic_pack(source, scratch, face):
    path = scratch / f"copycat-window-{face}.hmod"
    replacements = {}
    for family, color in zip(("oak", "birch"), COLORS, strict=True):
        name = f"create:block/{family}_culling_marker"
        marker = {
            "textures": {"marker": name},
            "elements": [{
                "from": [0, 0, 0], "to": [16, 16, 16],
                "faces": {face: {"texture": "#marker", "cullface": face}},
            }],
        }
        replacements[f"assets/create/blockstates/{family}_window.json"] = json.dumps({"variants": {"": {"model": name}}})
        replacements[f"assets/create/models/block/{family}_culling_marker.json"] = json.dumps(marker)
        replacements[f"assets/create/textures/block/{family}_culling_marker.png"] = window.diagnostic_tile(color)
    with ZipFile(source) as original, ZipFile(path, "w", ZIP_DEFLATED) as output:
        for entry in original.infolist():
            marker = replacements.pop(entry.filename, None)
            disabled = entry.filename.endswith(".properties") and any(
                f"/ctm/{family}_window/" in entry.filename for family in ("oak", "birch")
            )
            if not disabled:
                output.writestr(entry, original.read(entry) if marker is None else marker)
        for name, marker in replacements.items():
            output.writestr(name, marker)
    return path


def block_set(row):
    own = f"create:{row['subject']}_window"
    other_family = "birch" if args.painted or row["subject"] == "oak" else "oak"
    other = f"create:{other_family}_window"
    face = row["face"]
    outward = "north" if face == "south" else "south"
    return own, {
        "air": ("minecraft:air", None),
        "same-window": (own, None),
        "other-window": (other, None),
        "inward-panel": (f"create:copycat_panel[facing={face}]", own),
        "outward-panel": (f"create:copycat_panel[facing={outward}]", own),
        "other-material-panel": (f"create:copycat_panel[facing={face}]", other),
        "step": (f"create:copycat_step[facing={face},half=bottom]", own),
    }[row["neighbor"]]


def painted_blocks(row):
    face = row["face"]
    outward = "north" if face == "south" else "south"
    inward_panel = f"create:copycat_panel[facing={face}]"
    outward_panel = f"create:copycat_panel[facing={outward}]"
    out_step = f"create:copycat_step[facing={outward},half=bottom]"
    in_step = f"create:copycat_step[facing={face},half=bottom]"
    own = {
        "panel-inward": inward_panel,
        "panel-outward": outward_panel,
        "step-inward": in_step,
        "step-outward": out_step,
    }[row["subject"]]
    neighbour = {
        "air": ("minecraft:air", None),
        "oak": ("create:oak_window", None),
        "birch": ("create:birch_window", None),
        "oak-panel-inward": (inward_panel, "create:oak_window"),
        "oak-panel-outward": (outward_panel, "create:oak_window"),
        "birch-panel-inward": (inward_panel, "create:birch_window"),
        "oak-step": (out_step, "create:oak_window"),
    }[row["neighbor"]]
    return own, neighbour


def run(args):
    with args.reference.open() as trace:
        rows = list(csv.DictReader(trace))
    failures = []
    with TemporaryDirectory(prefix="hc-copycat-culling-") as directory:
        scratch = Path(directory)
        screenshot = scratch / "frame.png"
        for face in ("north", "south"):
            pack = diagnostic_pack(args.pack or ROOT / ".local/create.hmod", scratch, face)
            with fixture_world(args, f"CopycatWindowCulling-{face}", render=True, pack=pack) as control:
                control.commands(("/time set noon", "/gamemode spectator"))
                control.call("key", "f1", "tap")
                direction = 1 if face == "south" else -1
                boundary = Z + (direction > 0)
                for row in (r for r in rows if r["face"] == face):
                    own, (neighbour, material) = painted_blocks(row) if args.painted else block_set(row)
                    control.commands((
                        window.block(X, Y, Z + direction),
                        window.block(X, Y, Z, own),
                        window.block(X, Y, Z + direction, neighbour),
                    ))
                    if args.painted:
                        wrapped.paint(control, X, Y, Z, "create:oak_window")
                    if material:
                        wrapped.paint(control, X, Y, Z + direction, material)
                    height = Y + (.25 if row["subject"].startswith("step") else .5)
                    control.call("tp", X + .5, height - 1.62, boundary + .08 * direction)
                    control.call("look-at", X + .5, height, boundary)
                    control.call("wait", 5)
                    control.call("screenshot", screenshot)
                    rgb = window.rgb_at(window.image(args.ffmpeg, screenshot, scaled=True), 319, 179)
                    marker = (
                        rgb[0] > 1.7 * rgb[1] and rgb[2] > 1.7 * rgb[1]
                        if args.painted or row["subject"] == "oak" else
                        rgb[1] > 1.7 * rgb[0] and rgb[2] > 1.7 * rgb[0]
                    )
                    if marker != (row["visible"] == "true"):
                        failures.append((row, rgb))
    for failure in failures:
        print(failure)
    if failures:
        raise RuntimeError(f"{len(failures)} of {len(rows)} Copycat shared-face culling decisions differed.")
    print(f"All {len(rows)} Java window and painted Copycat shared-face decisions matched Horizon's framebuffer.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for attribute in ("ctl", "client", "resources"):
        parser.add_argument(attribute, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--painted", action="store_true")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    if args.reference is None:
        filename = "copycat-painted-culling-java.csv" if args.painted else "copycat-window-culling-java.csv"
        args.reference = ROOT / "fixtures" / filename
    run(args)
