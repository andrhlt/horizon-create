#!/usr/bin/env python3
"""Replay Java Encased Fluid Pipe drain fittings through the Horizon renderer."""

import argparse
import csv
from collections import defaultdict
from contextlib import ExitStack
import importlib
from pathlib import Path
import re
from shutil import which
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from fixture_world import ROOT, fixture_world

mp = importlib.import_module("test-multiplayer")
window = importlib.import_module("test-window-ctm")

ENV = {"CREATE_ENCASED_PIPE_DRAIN_TRACE": "1", "HORIZON_NO_AUDIO": "1"}
RENDERED = re.compile(rb"CREATE_ENCASED_PIPE_DRAIN (-?\d+),(-?\d+),(-?\d+),([a-z|]*),(\d+)")
ARTWORK = "assets/create/textures/block/pipes.png"
PARTS = ("rim_connector", "drain")
NORMALS = {
    "down": (0, -1, 0), "up": (0, 1, 0), "north": (0, 0, -1),
    "south": (0, 0, 1), "west": (-1, 0, 0), "east": (1, 0, 0),
}
PIPE = "create:encased_fluid_pipe"
GUEST = "PipeDrainGuest"
VISION_Y = 232


def diagnostic_pack(args, scratch):
    diagnostic = scratch / "diagnostic.hmod"
    originals = [ARTWORK]
    originals.extend(f"assets/create/models/block/fluid_pipe/{part}/{face}.json"
                     for part in PARTS for face in NORMALS)
    with ZipFile(args.pack) as source, ZipFile(diagnostic, "w", ZIP_DEFLATED) as output:
        for path in originals:
            data = source.read(path)
            if args.java_source:
                assert data == (args.java_source / "src/main/resources" / path).read_bytes(), path
        for item in source.infolist():
            data = window.diagnostic_tile((24, 240, 28)) if item.filename == ARTWORK else source.read(item)
            output.writestr(item, data)
    if args.java_source:
        print("Matched all 12 directional Java models and their original pipes sprite byte for byte.")
    return diagnostic


def read_trace(actor, offset):
    path = actor.socket.parent / "ctl.log"
    with path.open("rb") as stream:
        stream.seek(offset)
        data = stream.read()
    return {(int(x), int(y), int(z)): (faces.decode(), int(parts))
            for x, y, z, faces, parts in RENDERED.findall(data)}


def build_face(host, rows):
    commands = ["/fill 0 194 0 32 198 26 minecraft:air"]
    expected = {}
    for index, row in enumerate(rows):
        pos = (3 + 4 * (index % 7), 196, 3 + 4 * (index // 7))
        face = row["face"]
        neighbor = tuple(a + b for a, b in zip(pos, NORMALS[face], strict=True))
        state = f"{PIPE}[{face}={row['open']}]"
        commands.extend((window.block(*neighbor, row["neighbor"]), window.block(*pos, state)))
        expected[pos] = ((face, 2) if row["fitting"] == "DRAIN" else ("", 0), row)
    host.commands(commands)
    return expected


def assert_rendered(actors, expected, start):
    def samples():
        return [read_trace(actor, offset) for actor, offset in zip(actors, start, strict=True)]

    current = samples()
    for _ in range(4):
        if all(all(sample.get(pos) == value for pos, (value, _) in expected.items()) for sample in current):
            return
        for actor in actors:
            actor.call("wait", 5)
        current = samples()
    failures = [(index, pos, row, sample.get(pos), value)
                for index, sample in enumerate(current)
                for pos, (value, row) in expected.items() if sample.get(pos) != value]
    raise RuntimeError(f"{len(failures)} fitting mismatches: {failures[:8]}")


def verify_visible_geometry(args, actors, scratch):
    host = actors[0]
    pos = (12, 196, 12)
    neighbor = (13, 196, 12)
    host.commands(("/fill 0 194 0 32 198 26 minecraft:air", window.block(*pos, f"{PIPE}[east=true]")))
    host.command("/tp @s 15.0 196.4 15.75")
    if len(actors) == 2:
        host.command(f"/tp {GUEST} 15.0 196.4 15.75")
        mp.until("the guest to reach the fitting", lambda: actors[1].call("state")["player"]["position"] == [15.0, 196.4, 15.75])
    for actor in actors:
        actor.call("look-at", 13.05, 196.5, 12.5)
        actor.call("wait", 2)
    for adjacent in ("minecraft:air", "create:item_drain", "minecraft:air"):
        offsets = [(actor.socket.parent / "ctl.log").stat().st_size for actor in actors]
        host.command(window.block(*neighbor, adjacent))
        present = adjacent == "create:item_drain"
        assert_rendered(actors, {pos: (("east", 2) if present else ("", 0), adjacent)}, offsets)
        for index, actor in enumerate(actors):
            frame = scratch / f"drain-{index}.png"
            actor.call("screenshot", frame)
            rgba = window.image(args.ffmpeg, frame, scaled=True)
            matching = sum(g > 60 and g > 2 * max(r, b) for r, g, b in
                           zip(rgba[::4], rgba[1::4], rgba[2::4], strict=True))
            if (matching > 10) != present:
                raise RuntimeError(f"Client {index} drew {matching} fitting pixels next to {adjacent}")
    print("The fitting appeared in the offscreen frame and disappeared when the neighbor was removed.")


def run(args, scratch):
    pack = diagnostic_pack(args, scratch)
    with (ROOT / "fixtures/encased-pipe-drain-fitting-java.csv").open() as source:
        reference = defaultdict(list)
        for row in csv.DictReader(source):
            reference[row["face"]].append(row)

    with ExitStack() as stack:
        suffix = "Lan" if args.lan else "Solo"
        host = stack.enter_context(fixture_world(args, f"EncasedDrain{suffix}", render=True, pack=pack, env=ENV))
        host.commands(("/time set noon", "/gamemode spectator", f"/tp @s 15.5 {VISION_Y} 12.5"))
        actors = [host]
        if args.lan:
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            guest = stack.enter_context(mp.joined_client(args, scratch, f"127.0.0.1:{port}",
                                                       GUEST, render=True, scenario="encased-drain",
                                                       pack=pack, env=ENV))
            mp.until("guest placement", lambda: any(row["name"] == GUEST and row["placed"]
                                                  for row in host.call("lan", "status")["guests"]))
            host.commands((f"/gamemode spectator {GUEST}", f"/tp {GUEST} 15.5 {VISION_Y} 12.5"))
            mp.until("guest fixture view", lambda: guest.call("state")["player"]["position"][1] == VISION_Y)
            actors.append(guest)
        for actor in actors:
            actor.call("key", "f1", "tap")
            actor.call("look-at", 15.5, 196, 12.5)
            actor.call("wait-ready")
        for face, rows in reference.items():
            offsets = [(actor.socket.parent / "ctl.log").stat().st_size for actor in actors]
            expected = build_face(host, rows)
            assert_rendered(actors, expected, offsets)
            print(f"Matched {len(rows)} Java {face} fitting selections on {len(actors)} rendered client(s).", flush=True)
        verify_visible_geometry(args, actors, scratch)
    print(f"Matched all {sum(map(len, reference.values()))} Java fitting selections.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--java-source", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    if not which(args.ffmpeg):
        parser.error("the offscreen fixture requires ffmpeg")
    with TemporaryDirectory(prefix="hc-encased-drain-") as scratch:
        run(args, Path(scratch))
