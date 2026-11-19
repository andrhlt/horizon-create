#!/usr/bin/env python3
"""Compare directed Java window occlusion with actual rendered Horizon faces."""

import argparse
import csv
import importlib.util
import json
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from fixture_world import ROOT, fixture_world

X, Y, Z = 8, 190, 8
AZIMUTHS = {"east": (1, 0, 0), "up": (0, 1, 0)}
MARKER = "create:block/window_culling_probe"
STATE_PROPERTIES = {"e": "east", "w": "west", "n": "north",
                    "s": "south", "water": "waterlogged"}


def load_visual_helpers():
    spec = importlib.util.spec_from_file_location("window_diagnostic", ROOT / "tools/test-window-ctm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


window = load_visual_helpers()


def face_model(start, finish, facing):
    faces = {side: {"texture": f"#{side}", "cullface": side} for side in facing}
    textures = {side: MARKER for side in (*facing, "particle")}
    return {"textures": textures, "elements": [{"from": start, "to": finish, "faces": faces}]}


def diagnostic_pack(pack, scratch, subjects, neighbors):
    path = scratch / "window-culling-diagnostic.hmod"
    models = {
        "full": face_model([0, 0, 0], [16, 16, 16], ("up", "east")),
        "post": face_model([7, 0, 7], [9, 16, 9], ("up",)),
        "arm": face_model([9, 0, 7], [16, 16, 9], ("east",)),
    }
    def model(name):
        return {"model": f"create:block/window_culling_probe_{name}"}
    full = {"variants": {"": model("full")}}
    pane = {"multipart": [{"apply": model("post")}, {"when": {"east": "true"}, "apply": model("arm")}]}
    replaced = {f"assets/create/blockstates/{key.removeprefix('create:')}.json":
                   pane if key.endswith("_pane") else full
                for key in subjects | {key for key in neighbors if key.startswith("create:")}}
    with ZipFile(pack) as source, ZipFile(path, "w", ZIP_DEFLATED) as output:
        for item in source.infolist():
            definition = replaced.pop(item.filename, None)
            output.writestr(item, source.read(item) if definition is None else json.dumps(definition))
        for name, definition in replaced.items():
            output.writestr(name, json.dumps(definition))
        for role, geometry in models.items():
            output.writestr(f"assets/create/models/block/window_culling_probe_{role}.json", json.dumps(geometry))
        output.writestr("assets/create/textures/block/window_culling_probe.png",
                        window.diagnostic_tile((250, 18, 235)))
    return path


def with_shape(name, shape):
    props = [f"{STATE_PROPERTIES[key]}=true" for key in shape.split("+") if key]
    return f"{name}[{','.join(props)}]" if props else name


def build_case(control, row):
    own = with_shape(row["subject"], row["subject_state"])
    other = with_shape(row["neighbor"], row["neighbor_state"])
    dx, dy, dz = AZIMUTHS[row["face"]]
    control.commands((
        window.block(X, Y + 1, Z), window.block(X + 1, Y, Z),
        window.block(X + dx, Y + dy, Z + dz, other), window.block(X, Y, Z, own),
    ))
    x, y, z = (origin + 0.5 + delta * 0.5
               for origin, delta in zip((X, Y, Z), (dx, dy, dz), strict=True))
    # Look from inside the adjacent cell. The diagnostic model supplies no
    # west/down faces, so only the subject can paint the shared interface.
    control.call("tp", x + 0.44 * dx, y + 0.44 * dy - 1.62, z + 0.44 * dz)
    control.call("look-at", x, y, z)
    control.call("wait", 3)


def run(args, scratch):
    with (ROOT / "fixtures/window-culling-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    subjects = {row["subject"] for row in rows}
    neighbors = {row["neighbor"] for row in rows}
    pack = diagnostic_pack(args.pack, scratch, subjects, neighbors)
    differences = []
    with fixture_world(args, "WindowCulling", render=True, pack=pack) as control:
        control.commands(("/time set noon", "/gamemode spectator", "/effect give @s minecraft:night_vision infinite 0 true"))
        control.call("key", "f1", "tap")
        for row in rows:
            build_case(control, row)
            frame = scratch / "frame.png"
            control.call("screenshot", frame)
            pixels = window.image(args.ffmpeg, frame, scaled=True)
            red, green, blue = window.rgb_at(pixels, 319, 179)
            actual = red > 75 and blue > 75 and red > 1.55 * green and blue > 1.45 * green
            expected = row["visible"] == "true"
            case = (row["subject"], row["subject_state"], row["neighbor"], row["neighbor_state"], row["face"])
            print(f"{case}: Horizon {actual}, Java {expected}, marker RGB {(red, green, blue)}", flush=True)
            if actual != expected:
                differences.append((case, actual, expected))
    if differences:
        print(f"{len(differences)} of {len(rows)} Horizon faces disagreed with Java.")
        for difference in differences:
            print(f"WINDOW_CULL_DIFFERENCE {difference}")
        raise RuntimeError("Window face culling differs from Java.")
    print(f"Matched all {len(rows)} directed window faces against Java.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    if not which(args.ffmpeg):
        parser.error("window culling framebuffer verification requires ffmpeg")
    with TemporaryDirectory(prefix="hc-window-culling-") as directory:
        run(args, Path(directory))


if __name__ == "__main__":
    main()
