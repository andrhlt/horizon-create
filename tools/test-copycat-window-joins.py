#!/usr/bin/env python3
"""Replay Java's connected tile decisions on windows adjacent to Copycat blocks."""
import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

copycat = import_module("test-copycat")
window = import_module("test-window-ctm")
multiplayer = import_module("test-multiplayer")
X, Y, Z = 8, 111, -10
CASES = {
    "air": ("minecraft:air", None),
    "oak": ("create:oak_window", None),
    "birch": ("create:birch_window", None),
    "oak-panel-inward": ("create:copycat_panel[facing=south]", "create:oak_window"),
    "oak-panel-outward": ("create:copycat_panel[facing=north]", "create:oak_window"),
    "birch-panel": ("create:copycat_panel[facing=north]", "create:birch_window"),
    "front-birch-panel": ("create:copycat_panel[facing=south]", "create:birch_window"),
    "oak-step": ("create:copycat_step[facing=north,half=bottom]", "create:oak_window"),
}

def run(args):
    with args.reference.open() as trace:
        rows = list(csv.DictReader(trace))
    failures = []
    with TemporaryDirectory(prefix="copycat-window-") as directory:
        scratch = Path(directory)
        pack = window.diagnostic_pack(args.pack or ROOT / ".local/create.hmod", scratch)
        with fixture_world(args, "CopycatWindowDirections", render=True, pack=pack) as control:
            control.commands(("/time set noon", "/gamemode spectator", window.block(X, Y, Z, "create:oak_window")))
            control.call("key", "f1", "tap")
            for row in rows:
                face = row["face"]
                dy = 1 if row["toward"] == "up" else -1
                neighbour = row["neighbor"]
                frontal = neighbour.startswith("front-")
                target_z = Z + (1 if face == "south" else -1) if frontal else Z
                case = neighbour if neighbour == "front-birch-panel" else neighbour.removeprefix("front-")
                state, material = CASES[case]
                # The Java probe names the Panel orientations relative to the viewed face.
                if face == "north" and "facing=" in state:
                    original = "north" if "facing=north" in state else "south"
                    flipped = "south" if original == "north" else "north"
                    state = state.replace(f"facing={original}", f"facing={flipped}")
                commands = [
                    window.block(X, Y + height, z)
                    for height in (-1, 1) for z in (Z - 1, Z, Z + 1)
                ]
                if frontal:
                    commands.append(window.block(X, Y + dy, Z, "create:oak_window"))
                commands.append(window.block(X, Y + dy, target_z, state))
                control.commands(commands)
                if material is not None:
                    nbt = '{Material:{Name:"%s"},Item:{id:"%s",count:1}}' % (material, material)
                    control.command(f"/data merge block {X} {Y + dy} {target_z} {nbt}")
                control.call("tp", X + 0.5, Y - 1, Z + (3.8 if face == "south" else -2.8))
                control.call("look-at", X + 0.5, Y + 0.5, Z + 0.5)
                control.call("wait", 5)
                frame = scratch / "frame.png"
                control.call("screenshot", frame)
                expected = int(row["tile"])
                label = (row["neighbor"], row["toward"], face)
                try:
                    window.check_frame(window.image(args.ffmpeg, frame, scaled=True), 0, expected, label, False)
                except RuntimeError as error:
                    failures.append(str(error))
    for failure in failures:
        print(failure)
    if failures:
        raise RuntimeError(f"{len(failures)} of {len(rows)} Java window join observations differed.")
    print(f"All {len(rows)} original Java window joins matched Horizon's framebuffer.")

def save_reload(args):
    with TemporaryDirectory(prefix="hc-copycat-save-") as directory:
        scratch = Path(directory)
        pack = window.diagnostic_pack(args.pack or ROOT / ".local/create.hmod", scratch)
        with fixture_world(args, "CopycatWindowSave", render=True, pack=pack) as control:
            panel = "create:copycat_panel[facing=north]"
            control.commands((
                "/time set noon", "/gamemode spectator",
                window.block(X, Y, Z, "create:oak_window"), window.block(X, Y + 1, Z, panel),
                f'/data merge block {X} {Y+1} {Z} {{Material:{{Name:"create:oak_window"}},Item:{{id:"create:oak_window",count:1}}}}',
            ))
            frame = scratch / "frame.png"

            def view():
                control.call("key", "f1", "tap")
                control.call("tp", X + .5, Y - 1, Z + 3.8)
                control.call("look-at", X + .5, Y + .5, Z + .5)

            def has_tile(expected):
                control.call("screenshot", frame)
                try:
                    window.check_frame(window.image(args.ffmpeg, frame, scaled=True), 0, expected, "Oak Window", False)
                except RuntimeError:
                    return False
                return True

            view()
            multiplayer.until("connected tile before save", lambda: has_tile(1))
            control.stop()
            control.open()
            view()
            multiplayer.until("connected tile after save reload", lambda: has_tile(1))
            control.commands((window.block(X, Y + 1, Z), window.block(X, Y + 1, Z, panel)))
            multiplayer.until("standalone tile after the Panel is replaced", lambda: has_tile(0))
    print("The copycat join survived world reload and cleared when the Panel was replaced.")


def copycat_persistence(args):
    with fixture_world(args, "CopycatMaterialSave", pack=args.pack) as control:
        panel = (8, 111, -10)
        step = (9, 111, -10)
        base = (10, 111, -10)
        control.commands((
            "/fill 7 110 -11 11 110 -9 minecraft:stone",
            f"/setblock {panel[0]} {panel[1]} {panel[2]} create:copycat_panel[facing=north,waterlogged=false]",
            f'/data merge block {panel[0]} {panel[1]} {panel[2]} {{Material:{{Name:"create:oak_window"}},Item:{{id:"create:oak_window",count:1}}}}',
            f"/setblock {step[0]} {step[1]} {step[2]} create:copycat_step[facing=east,half=top,waterlogged=false]",
            f'/data merge block {step[0]} {step[1]} {step[2]} {{Material:{{Name:"minecraft:oak_log",Properties:{{axis:"x"}}}},Item:{{id:"minecraft:oak_log",count:1}}}}',
            f"/setblock {base[0]} {base[1]} {base[2]} create:copycat_panel[facing=south,waterlogged=false]",
        ))
        expected = {
            panel: ("create:copycat_panel", {"facing": "north", "waterlogged": "false"}, ("create:oak_window", {})),
            step: ("create:copycat_step", {"facing": "east", "half": "top", "waterlogged": "false"}, ("minecraft:oak_log", {"axis": "x"})),
            base: ("create:copycat_panel", {"facing": "south", "waterlogged": "false"}, ("create:copycat_base", {})),
        }

        def verify():
            for pos, (block, properties, material) in expected.items():
                state = control.call("block", *pos)["state"]
                name, bracket, encoded = state.partition("[")
                observed = dict(pair.split("=", 1) for pair in encoded[:-1].split(",")) if bracket else {}
                if (name, observed) != (block, properties) or copycat.material_tag(control, pos) != material:
                    return False
            return True

        multiplayer.until("Copycat material and shape before save", verify)
        control.stop()
        control.open()
        multiplayer.until("Copycat material and shape after save reload", verify)
    print("Copycat Panel, Step and base material/shape identities survived an idle save and reopen.")


def copycat_bars_wrench(args):
    with fixture_world(args, "CopycatBarsWrench", pack=args.pack) as control:
        pos = (8, 111, -10)
        control.commands((
            "/fill 3 110 -14 13 110 -6 minecraft:stone",
            f"/setblock {pos[0]} 113 {pos[2]} create:copycat_bars[facing=up]",
        ))
        control.call("command", "/gamemode creative")
        copycat.put(control, "create:wrench")
        control.command("/tp @s 8.5 111.0 -7.5 180 -10")
        control.call("wait", 3)
        control.call("command", "/gamemode survival")
        control.call("wait", 1)
        cases = (
            ("south", "east", (8.5, 111.0, -7.5), 180, (8.5, 113.1, -9.0)),
            ("north", "east", (8.5, 111.0, -12.5), 0, (8.5, 113.1, -10.0)),
            ("east", "north", (11.5, 111.0, -9.5), -90, (9.0, 113.1, -9.5)),
            ("west", "north", (4.5, 111.0, -9.5), 90, (8.0, 113.1, -9.5)),
        )
        for face, expected, approach, yaw, target in cases:
            control.command(f"/setblock {pos[0]} 113 {pos[2]} create:copycat_bars[facing=up]")
            control.command(f"/tp @s {approach[0]} {approach[1]} {approach[2]} {yaw} -10")
            control.call("wait", 1)
            if target is not None:
                control.call("look-at", *target)
                control.call("wait", 1)
                hit = control.call("looking-at").get("block")
                if not hit or hit["pos"] != [pos[0], 113, pos[2]] or hit["face"] != face:
                    raise RuntimeError(f"Copycat Bars Wrench missed the {face} face: {hit}")
            tick = control.clock()
            result = control.call("mouse", "right", "click")
            if result.get("ok") is False:
                raise RuntimeError(f"Copycat Bars Wrench {face} mouse click failed: {result}")
            multiplayer.until(f"Copycat Bars Wrench {face} rotation", lambda: (
                control.call("block", pos[0], 113, pos[2])["state"] == f"create:copycat_bars[facing={expected}]"
            ))
            print(f"Copycat Bars {face}: {control.call('block', pos[0], 113, pos[2])['state']}")
            if control.clock() != tick:
                raise RuntimeError("Copycat Bars rotation advanced the frozen world")
    print("Copycat Bars Wrench rotations matched south/east/north/west face cases on the matching build.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for attribute in ("ctl", "client", "resources"):
        parser.add_argument(attribute, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/copycat-window-joins-java.csv")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--save-reload", action="store_true")
    parser.add_argument("--copycat-persistence", action="store_true")
    parser.add_argument("--copycat-bars-wrench", action="store_true")
    args = parser.parse_args()
    action = copycat_bars_wrench if args.copycat_bars_wrench else copycat_persistence if args.copycat_persistence else save_reload if args.save_reload else run
    action(args)
