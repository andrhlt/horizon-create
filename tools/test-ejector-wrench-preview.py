#!/usr/bin/env python3
"""Check original Wrench outlines and emitted trajectory dust in Horizon."""
from argparse import ArgumentParser
from collections import Counter
import csv
from math import isclose
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from struct import pack, unpack
import os
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

multiplayer = import_module("test-multiplayer")
GUEST = "EjectVizGuest"
WRENCH = "create:wrench"
RIGS = (
    (-11, "east", 4, 0, "9 104 -11 minecraft:smooth_stone", "3.5 104 -10.5"),
    (-27, "west", 3, 1, "2 105 -27 minecraft:smooth_stone_slab[type=bottom]", "7.5 104 -26.5"),
    (-43, "south", 7, -2, "5 102 -36 minecraft:air", "5.5 104 -40.5"),
)


def read_since(log, offset):
    with log.open("rb") as stream:
        stream.seek(offset)
        return stream.read().decode(errors="replace")


def f32(value):
    return unpack("!f", pack("!f", value))[0]


def compare_dust(metadata, dust, reference):
    x, y, z, dx, dz, horizontal, vertical, count = map(int, metadata[:8])
    render_time, spacing = map(float, metadata[8:10])
    expected_geometry = tuple(int(reference[key]) for key in (
        "x", "y", "z", "dx", "dz", "horizontal", "vertical", "dust_count",
    ))
    if (x, y, z, dx, dz, horizontal, vertical, count) != expected_geometry:
        raise RuntimeError(f"Wrong Ejector path geometry: {metadata}. Expected {expected_geometry}.")
    if metadata[-1] != reference["dust_color"] or not isclose(spacing, float(reference["dust_spacing"]), abs_tol=1e-8):
        raise RuntimeError(f"Wrong Ejector dust color or spacing: {metadata}.")
    across, upwards, flight_ticks = (float(reference[key]) for key in ("x_motion", "y_motion", "flight_ticks"))
    phase = f32(f32(render_time) / 3.0) % spacing
    for i, row in enumerate(dust):
        time = phase + i * spacing
        horizontal_motion = f32(-10.6033 * across * (0.91 ** time - 1))
        drag = 0.98 ** time
        vertical_motion = f32(-49.4983 * upwards * drag + 49.4983 * upwards - 194.033 * drag - 3.92 * time + 194.033)
        correction = min(time / flight_ticks, 1) ** 3
        distance = horizontal_motion + (horizontal - horizontal_motion) * correction
        height = vertical_motion + (vertical - vertical_motion) * correction * 0.5
        expected = (i, time, x + .5 + dx * distance, y + .5 + height, z + .5 + dz * distance)
        if not all(isclose(float(a), b, abs_tol=2e-6) for a,b in zip(row, expected, strict=True)):
            raise RuntimeError(f"Ejector dust at {x, y, z}: expected Java {expected}, observed {row}.")


def verify(samples, reference):
    trace = "\n".join(samples)
    prefix = "CREATE_EJECTOR_WRENCH_"
    # A client log can interleave stderr writes. Reject partial records and
    # still require a complete shape observation from every target.
    outline_row = r"(-?\d+,-?\d+,-?\d+,(?:-?\d+\.\d+,){6}[0-9a-f]{6},\d+\.\d+)$"
    bounds = set(re.findall(rf"^{prefix}OUTLINE {outline_row}", trace, flags=re.M))
    expected_bounds = {",".join(row[key] for key in (
        "target_x","target_y","target_z","min_x","min_y","min_z","max_x","max_y","max_z","outline_color","line_width",
    )) for row in reference.values()}
    if bounds != expected_bounds:
        raise RuntimeError(f"Wrench target bounds expected {expected_bounds}, observed {bounds}.")

    frames = Counter()
    particles = 0
    for chunk in trace.split(prefix + "ARC ")[1:]:
        header = chunk.splitlines()[0].split(",")
        rows = [line.split(",") for line in re.findall(rf"{prefix}DUST ([^\r\n]+)", chunk)]
        if len(header) != 11 or len(rows) != int(header[7]):
            continue
        z = int(header[2])
        compare_dust(header, rows, reference[z])
        frames[z] += 1
        particles += len(rows)
    if frames.keys() != reference.keys() or min(frames.values()) < 4:
        raise RuntimeError(f"Incomplete Ejector render observations: {frames}.")
    return particles, sum(frames.values())


def main():
    parser = ArgumentParser()
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--reference", type=Path, default=ROOT / "fixtures/weighted-ejector-wrench-java.csv")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    os.environ["CREATE_EJECTOR_WRENCH_PREVIEW"] = "1"
    role = "LAN" if args.lan else "Solo"
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, f"EjectorWrench{role}", render=True, pack=args.pack))
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-eject-viz-")))
            actor = stack.enter_context(multiplayer.joined_client(
                args, scratch, f"127.0.0.1:{port}", GUEST, render=True, scenario="eject-viz", pack=args.pack))
            multiplayer.until("guest in the Wrench preview world", lambda:
                              any(p["name"] == GUEST and p["placed"] for p in host.call("lan", "status")["guests"]))
            name = GUEST
        else:
            actor, name = host, "@s"
        host.command(f"/give {name} {WRENCH}")
        multiplayer.until("player has a Wrench", lambda: multiplayer.count(actor, WRENCH) == 1)
        actor.call("select", WRENCH)
        host.command("/tick unfreeze")
        log = actor.socket.parent / "ctl.log"
        samples = []
        for z, facing, h, v, target, view in RIGS:
            offset = log.stat().st_size
            commands = (
                f"/fill 0 103 {z-2} 12 103 {z+2} minecraft:smooth_stone",
                f"/setblock {target}",
                f"/setblock 5 104 {z} create:weighted_ejector[facing={facing}]{{HorizontalDistance:{h},VerticalDistance:{v}}}",
                f"/tp {name} {view}",
            )
            for command in commands:
                host.call("command", command)
            multiplayer.until("player near the Ejector", lambda:
                              actor.call("state")["player"]["position"] == list(map(float, view.split())))
            actor.call("look-at", 5.5, 104.55, z + .5)
            multiplayer.until("player sees the Ejector", lambda:
                              (actor.call("looking-at").get("block") or {}).get("pos") == [5, 104, z])
            arc = f"CREATE_EJECTOR_WRENCH_ARC 5,104,{z},"
            multiplayer.until("five Ejector arc emissions", lambda: read_since(log, offset).count(arc) >= 5)
            text = read_since(log, offset)
            samples.extend(re.findall(r"CREATE_EJECTOR_WRENCH_(?:ARC|DUST|OUTLINE) [^\r\n]+", text))
            if args.screenshot and z == -11:
                actor.call("screenshot", args.screenshot)
        actor.call("select", 9)
        actor.call("wait", 2)
        offset = log.stat().st_size
        actor.call("wait", 5)
        if "CREATE_EJECTOR_WRENCH_" in read_since(log, offset):
            raise RuntimeError("The preview kept emitting after the Wrench was put away.")
    if args.trace:
        args.trace.write_text("\n".join(samples) + "\n")
    with args.reference.open() as stream:
        reference = {int(row["z"]): row for row in csv.DictReader(stream)}
    particles, frames = verify(samples, reference)
    print(f"{role} matched {particles} Java particle positions over {frames} emissions and {len(reference)} target outlines.")


if __name__ == "__main__":
    main()
