#!/usr/bin/env python3
"""Observe the Frogport opening for two menu viewers and closing after the last leaves."""

import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

menu = import_module("test-frogport-menu")
multiplayer = menu.multiplayer
PORT = menu.PORT
TRACE = re.compile(r"CREATE_FROGPORT_OPEN_TICK \[12, 100, -9\],(\d+),(\d+),([\d.]+),(true|false)")
SOUND = re.compile(r"CREATE_FROGPORT_SOUND \[12, 100, -9\],\d+,create:frogport_(open|close),([\d.]+),([\d.]+)(?:,(\d+))?")
MODEL = re.compile(r"CREATE_FROGPORT_MODEL \[12, 100, -9\],([^\r\n]+)")
ENV = {"CREATE_FROGPORT_OPEN": "1", "CREATE_CHAIN_RENDER": "1", "HORIZON_NO_AUDIO": "1"}


def logs(actor):
    return (actor.socket.parent / "ctl.log").read_text()


def samples(actor, offset):
    return [(int(tick), int(viewers), float(phase), closed == "true")
            for tick, viewers, phase, closed in TRACE.findall(logs(actor)[offset:])]


def settled(actor, offset, viewers, phase):
    observations = samples(actor, offset)
    return bool(observations and observations[-1][1:3] == (viewers, phase))


def cues(actor, offset):
    return [(event, float(volume), float(pitch), int(delay or 0))
            for event, volume, pitch, delay in SOUND.findall(logs(actor)[offset:])]


def assert_phases(actor, offset):
    records = samples(actor, offset)
    opening = [row for row in records if row[1] == 1][:3]
    closing = [row for row in records if row[1] == 0][:3]
    with (ROOT / "fixtures/frogport-manual-open-java.csv").open(newline="") as stream:
        java = {int(row["tick"]): row for row in csv.DictReader(stream) if row["partial"] == "1.00"}
    for observed, ticks in ((opening, (1, 2, 3)), (closing, (8, 9, 10))):
        assert len(observed) == 3 and observed[2][0] - observed[0][0] == 2, observed
        for row, tick in zip(observed, ticks, strict=True):
            assert abs(row[2] - float(java[tick]["progress"])) < 1e-6, (row, java[tick])
            assert row[3] == (java[tick]["close"] == "true"), (row, java[tick])

    previous = current = 0.0
    moving_frames = 0
    for line in logs(actor)[offset:].splitlines():
        tick = TRACE.search(line)
        if tick:
            previous, current = current, float(tick[3])
            continue
        model = MODEL.search(line)
        if not model:
            continue
        _, partial, _, _, pitch, _, tongue, _, vertices = model[1].split(",")
        phase = previous + (current - previous) * float(partial)
        assert abs(float(pitch) - 60 * phase) < 2e-5, (line, previous, current)
        assert abs(float(tongue) - 0.25 * phase) < 1e-6, (line, previous, current)
        if 0 < phase < 1 and int(vertices) > 0:
            moving_frames += 1
    assert moving_frames >= 3, moving_frames
    close = [entry for entry in cues(actor, offset) if entry[0] == "close"]
    assert len(close) == 1 and close[0][1] == 1 and 1.25 <= close[0][2] < 1.5 and close[0][3] == 0, close


def run(args):
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "FrogportOpenLan", pack=args.pack, render=True, env=ENV))
        host.commands((
            "/fill 9 99 -10 35 99 -5 minecraft:stone",
            "/setblock 12 100 -9 create:package_frogport",
            "/tp @s 11.75 100 -6.5",
        ))
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-frogport-open-")))
        guest = stack.enter_context(multiplayer.joined_client(
            args, scratch, f"127.0.0.1:{port}", "LidObserver", pack=args.pack, render=True,
            scenario="frogport-opening", env=ENV,
        ))
        multiplayer.until("the Frogport observer to join", lambda:
                          any(g["name"] == "LidObserver" and g["placed"] for g in host.call("lan", "status")["guests"]))
        host.commands(("/gamemode survival @a", "/tp LidObserver 13.0 100 -6.25", "/tick unfreeze"))
        multiplayer.until("the observer to reach the Frogport", lambda:
                          guest.call("state")["player"]["position"] == [13.0, 100.0, -6.25])
        for actor in (host, guest):
            actor.call("look-at", 12.5, 100.55, -8.5)
            actor.call("wait", 4)
        offsets = [(actor, len(logs(actor))) for actor in (host, guest)]

        def both(viewers, phase):
            return all(settled(actor, offset, viewers, phase) for actor, offset in offsets)

        host.call("interact", *PORT, "south")
        multiplayer.until("both players to see the first open Frogport", lambda: both(1, 1))
        assert cues(*offsets[0]) == [("open", 0.5, 2.0, 0)]
        assert cues(*offsets[1]) == []

        guest.call("interact", *PORT, "south")
        multiplayer.until("both players to see two viewers", lambda: both(2, 1))
        assert cues(*offsets[1]) == [("open", 0.5, 2.0, 0)]

        host.call("close")
        multiplayer.until("the remaining viewer to hold the Frogport open", lambda: both(1, 1))
        assert all(len(cues(actor, offset)) == 1 for actor, offset in offsets)
        guest.call("close")
        multiplayer.until("both players to see the Frogport close", lambda:
                          all(any(sample[3] for sample in samples(actor, offset)) for actor, offset in offsets))
        host.call("wait", 5)
        for actor, offset in offsets:
            assert_phases(actor, offset)
        if args.distance:
            host.command("/tp LidObserver 25.5 100 -8.5")
            multiplayer.until("the listener to stand thirteen blocks away", lambda:
                              guest.call("state")["player"]["position"] == [25.5, 100.0, -8.5])
            guest.call("look-at", 12.5, 100.55, -8.5)
            distant_offset = len(logs(guest))
            host.call("interact", *PORT, "south")
            multiplayer.until("the distant view to open", lambda: settled(guest, distant_offset, 1, 1))
            host.call("close")
            multiplayer.until("the distant listener to queue the close", lambda: cues(guest, distant_offset))
            distant = cues(guest, distant_offset)
            assert len(distant) == 1 and distant[0][0] == "close" and distant[0][3] == 6, distant
            host.command("/tp LidObserver 33.5 100 -8.5")
            multiplayer.until("the listener to stand outside the close cue radius", lambda:
                              guest.call("state")["player"]["position"] == [33.5, 100.0, -8.5])
            distant_offset = len(logs(guest))
            host.call("interact", *PORT, "south")
            multiplayer.until("the far view to open", lambda: settled(guest, distant_offset, 1, 1))
            host.call("close")
            multiplayer.until("the far view to close", lambda:
                              any(sample[3] for sample in samples(guest, distant_offset)))
            assert not cues(guest, distant_offset), cues(guest, distant_offset)
            print("At thirteen blocks the closing cue was delayed six ticks. At twenty-one blocks it did not queue.")
    print("Both LAN clients saw the three Java opening and closing steps and one local open and nearby close cue each")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--distance", action="store_true")
    run(parser.parse_args())
