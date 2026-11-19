#!/usr/bin/env python3
"""Compare the stationary bearing receiver's original outline and draw offsets.

Apply java-mounted-storage-trace.patch, java-mounted-port-comparator-trace.patch,
java-mounted-port-idle-followup.patch and java-mounted-fixed-port-render.patch
to pinned Create, then run ./gradlew -PparityMountedComparator=idle runGameTestServer.
BEARING_FIXED_VISUAL records both interpolation endpoints and the original outline.

For the original live draw publication probe, copy the idle GameTest world's
world directory to run/bearing-port-client/saves/BearingPortDelivery, then run
./gradlew -PparityBearingPortClient runClient. JAVA_PSI_AUTH and JAVA_PSI_DRAW
record the server snapshot and actual Flywheel pose in the same process.
"""

import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
import os
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
mounted = import_module("test-mounted-storage")
REFERENCE = Path(__file__).resolve().parent.parent / "fixtures/mounted_fixed_port_render-java.csv"
PORT = (18, 98, -10)
STRUCTURE = Path("gametest/contraptions/mounted_item_extract.nbt")
RENDER_TICKS = (17, 19, 31, 32, 33, 34, 102, 103, 114, 115, 116, 117)
CLOSED_TICKS = (35, 101, 118)
FRAME_TICKS = (19, 31, 34, 35, 102, 118)
OUTLINE_TICKS = (17, 21, 34, 35, 103, 118)


def model(actor):
    return "extended=true" in actor.call("block", *PORT)["state"]


def reading(world):
    x, y, z = PORT
    keys = ("Timer", "Distance", "ExtensionPrevious", "ExtensionProgress", "ExtensionLit")
    values = (mounted.data(reply).rstrip("fb") for reply in world.commands(
        f"/data get block {x} {y} {z} {key}" for key in keys
    ))
    return tuple(float(value or 0) for value in values)


def draw_matches(log, beginning, row):
    with log.open("rb") as stream:
        stream.seek(beginning)
        for line in stream:
            _, frame, values = line.decode(errors="replace").partition("CREATE_TRAIN_PORT_FRAME ")
            if not frame:
                continue
            _, partial, previous, current, distance, yaw, pitch, lit, collar, tip, first, second = values.split()
            partial, previous, current, distance, collar, tip = map(
                float, (partial, previous, current, distance, collar, tip)
            )
            if (lit != row["lit"] or not isclose(distance * previous**2 / 2, float(row["tip_previous"]), abs_tol=2e-6)
                    or not isclose(distance * current**2 / 2, float(row["tip"]), abs_tol=2e-6)):
                continue
            assert isclose((previous + partial * (current - previous))**2 * distance / 2, tip, abs_tol=2e-6)
            assert isclose(collar, tip / 2 + .375, abs_tol=2e-6)
            assert (int(yaw), int(pitch), int(first), int(second)) == (-90, 90, 20, 136)
            return True
    return False

def run(args):
    flavor = "-lan" if args.multiplayer else ""
    label = f"mounted-fixed-port-render{flavor}"
    if args.baseline:
        label += "-baseline"
    image_dir = args.logs or ROOT / ".local"
    image_dir.mkdir(parents=True, exist_ok=True)
    rows = {}
    with REFERENCE.open() as f:
        rows = {int(row["tick"]): row for row in csv.DictReader(f)}
    differences = []
    missing_draws = []
    os.environ["CREATE_TRAIN_PORT_RENDER"] = ",".join(map(str, PORT))
    name = "BearingVisual"
    with ExitStack() as resources:
        world = resources.enter_context(fixture_world(args, label, STRUCTURE, render=True, pack=args.pack))
        start = world.clock()
        for tick in range(start + 1, start + (2 - start) % 20 + 1):
            world.step_to(tick)
        world.commands((
            "/place template create:gametest/contraptions/mounted_item_extract 14 96 -12",
            "/setblock 18 96 -10 minecraft:redstone_block",
            "/setblock 18 97 -10 minecraft:hopper[facing=north,enabled=false]",
        ))
        observer = world
        who = "@s"
        if args.multiplayer:
            port = world.call("lan", "open", "0", "commands", "force")["port"]
            scratch = resources.enter_context(TemporaryDirectory(prefix="hc-bearing-visual-"))
            observer = resources.enter_context(multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", name, render=True, scenario=label, pack=args.pack
            ))
            multiplayer.until("the bearing observer to enter", lambda: any(
                player["name"] == name and player["placed"] for player in world.call("lan", "status")["guests"]
            ))
            who = name
        world.command(f"/gamemode spectator {who}")

        def aim(at, target):
            world.command(f"/tp {who} {' '.join(map(str, at))}")
            observer.call("wait", 3)
            observer.call("look-at", *target)

        outline_camera = (16.6, 96.88, -9.5), (18.4, 98.5, -9.5)
        aim(*outline_camera)
        observer.call("key", "f1", "tap")
        world.command("/setblock 15 100 -11 minecraft:lever[face=wall,facing=north,powered=false]")
        start = world.clock()
        live_log = observer.socket.parent / "ctl.log"
        for tick in range(1, max(rows) + 1):
            beginning = live_log.stat().st_size if tick in RENDER_TICKS else 0
            world.step_to(start + tick)
            row = rows[tick]
            actual = reading(world)
            expected = tuple(float(row[key]) for key in ("timer", "distance", "previous", "current")) + (
                int(row["lit"] == "true"),
            )
            if any(not isclose(a, b, abs_tol=2e-6) for a, b in zip(actual, expected, strict=True)):
                differences.append((tick, "state", actual, expected))
            if tick in RENDER_TICKS or tick in CLOSED_TICKS:
                wanted = tick not in CLOSED_TICKS
                if model(world) != wanted:
                    differences.append((tick, "model", model(world), wanted))
                elif args.multiplayer:
                    multiplayer.until("the guest model to update", lambda: model(observer) == wanted)
                observer.call("wait", 3)
            if tick in OUTLINE_TICKS:
                result = observer.call("looking-at")
                hit = result.get("block") or {}
                point = hit.get("point")
                if (result.get("kind") != "block" or hit.get("pos") != list(PORT) or point is None
                        or not isclose(point[0] - PORT[0], float(row["min_x"]), abs_tol=1e-5)):
                    differences.append((tick, "west outline hit", result, row["min_x"]))
            if tick in FRAME_TICKS:
                aim((17.3, 99.6, -13), (17.7, 98.4, -9.5))
                observer.call("screenshot", image_dir / f"{label}-{tick}.png")
                aim(*outline_camera)
            if tick in RENDER_TICKS:
                observer.call("wait", 8)
                assert world.clock() == start + tick, "The host must stay frozen while observing the frame."
                if not draw_matches(live_log, beginning, row):
                    missing_draws.append(tick)
    log = (ROOT / f".local/{label}-{name.lower()}.log") if args.multiplayer else (
        ROOT / f".local/horizon-{label}.log"
    )
    if differences or missing_draws:
        raise RuntimeError(f"{len(differences)} state/outline differences, first {differences[:8]}. "
                           f"Missing Java-compatible rendered poses {missing_draws}. See {log}.")
    print(f"Matched {len(rows) - 1} Java visual state samples, {len(RENDER_TICKS)} rendered poses, "
          f"and {len(OUTLINE_TICKS)} original outlines over two docking cycles.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--logs", type=Path)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--multiplayer", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
