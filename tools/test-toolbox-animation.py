#!/usr/bin/env python3
"""Replay the Toolbox world opening and closing with a muted Horizon host and guest."""

import argparse
import csv
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

mp = import_module("test-toolbox-menu").mp
AT = (12, 100, -9)
PREFIX = r"\[12, 100, -9\]"
MOTION = re.compile(rf"CREATE_TOOLBOX_MOTION {PREFIX},(\d+),(\d+),([0-9.]+),([0-9.]+)")
CUE = re.compile(rf"CREATE_TOOLBOX_CUE {PREFIX},(\d+),minecraft:block\.([\w.]+),([0-9.]+),([0-9.]+),(\d+)")
PARTS = re.compile(rf"CREATE_TOOLBOX_PARTS {PREFIX},\d+,[0-9.]+,(-?[0-9.]+),([0-9.]+),([0-9.]+),(\d+)")
ENV = {"CREATE_TOOLBOX_ANIMATION": "1", "HORIZON_NO_AUDIO": "1"}


def log(actor):
    return (actor.socket.parent / "ctl.log").read_text()


def motion(readout):
    return [(int(tick), int(viewers), float(lid), float(drawers))
            for tick, viewers, lid, drawers in MOTION.findall(readout)]


def check(readout, java):
    timeline = motion(readout)
    opening = [point for point in timeline if point[1] > 0][:5]
    assert len(opening) == 5
    for (tick, _, lid, drawers), original in zip(opening, java[1:6], strict=True):
        assert tick == opening[0][0] + int(original["tick"]) - 1
        assert lid == float(original["lid_1"]), (tick, lid, original)
        assert drawers == float(original["drawers_1"]), (tick, drawers, original)

    first_close = next(index for index, row in enumerate(timeline) if row[1] == 0)
    closing = timeline[first_close:first_close + 3]
    assert len(closing) == 3
    for (tick, viewers, lid, _), original in zip(closing, java[8:11], strict=True):
        assert tick == closing[0][0] + int(original["tick"]) - 8
        assert viewers == 0 and lid == float(original["lid_1"]), (tick, viewers, lid, original)

    sounds = CUE.findall(readout)
    assert len(sounds) == 4, sounds
    expected = (
        (opening[0][0], "iron_door.open", 0.25, 1.2),
        (opening[0][0], "chest.open", 0.1, 1.1),
        (closing[0][0], "chest.close", 0.1, 1.1),
        (closing[0][0] + 5, "iron_door.close", 0.25, 1.2),
    )
    for (tick, cue, volume, pitch, delay), (when, event, gain, base_pitch) in zip(sounds, expected, strict=True):
        assert (int(tick), cue, float(volume), int(delay)) == (when, event, gain, 0), sounds
        assert base_pitch <= float(pitch) < base_pitch + 0.1, sounds

    parts = [(float(yaw), float(lid), float(drawers), int(vertices))
             for yaw, lid, drawers, vertices in PARTS.findall(readout)]
    assert parts and all(yaw == -90 and vertices > 0 for yaw, _, _, vertices in parts), parts[:20]
    assert any(lid == 135.0 and drawers > 0.0 for _, lid, drawers, _ in parts)
    assert any(0 < lid < 135 and 0 < drawers < 1 for _, lid, drawers, _ in parts)
    assert any(lid == 0 and drawers > 0 for _, lid, drawers, _ in parts)


def run(args):
    with (ROOT / "fixtures/toolbox-animation-java.csv").open(newline="") as stream:
        java = list(csv.DictReader(stream))
    with ExitStack() as stack:
        host = stack.enter_context(fixture_world(args, "ToolboxLidLan", pack=args.pack, render=True, env=ENV))
        host.commands((
            "/fill 8 99 -14 16 99 -4 minecraft:stone",
            "/setblock 12 100 -9 create:red_toolbox[facing=east]",
            "/tp @s 15.0 100 -8.25",
        ))
        port = host.call("lan", "open", "0", "commands", "force")["port"]
        scratch = Path(stack.enter_context(TemporaryDirectory(prefix="hc-tb-lid-")))
        guest = stack.enter_context(mp.joined_client(
            args, scratch, f"127.0.0.1:{port}", "ToolboxLidGuest", render=True,
            scenario="toolbox-animation", pack=args.pack, env=ENV,
        ))
        mp.until("the Toolbox observer to join", lambda: any(
            actor["name"] == "ToolboxLidGuest" and actor["placed"]
            for actor in host.call("lan", "status")["guests"]
        ))
        host.commands(("/tp ToolboxLidGuest 15.0 100 -9.75", "/tick unfreeze"))
        mp.until("the guest to reach the Toolbox", lambda:
                 guest.call("state")["player"]["position"] == [15, 100, -9.75])
        for actor in (host, guest):
            actor.call("look-at", 12.5, 100.5, -8.5)
            actor.call("wait", 3)
        offsets = [len(log(actor)) for actor in (host, guest)]

        def observations():
            return [log(actor)[offset:] for actor, offset in zip((host, guest), offsets, strict=True)]

        def both(viewers, lid):
            for evidence in observations():
                steps = motion(evidence)
                if not steps or steps[-1][1:3] != (viewers, lid):
                    return False
            return True

        host.call("interact", *AT, "east")
        mp.until("both clients to see one viewer open the Toolbox", lambda: both(1, 1.0))
        if args.screenshots:
            guest.call("screenshot", args.screenshots / "open.png")
        guest.call("interact", *AT, "east")
        mp.until("both clients to see two viewers", lambda: both(2, 1.0))
        host.call("close")
        mp.until("the guest to hold the Toolbox open", lambda: both(1, 1.0))
        guest.call("close")
        mp.until("both clients to close the Toolbox with its last sound cue", lambda:
                 all("iron_door.close" in evidence for evidence in observations()))
        host.call("wait", 5)
        if args.screenshots:
            host.call("screenshot", args.screenshots / "closing.png")
        for report in observations():
            check(report, java)
        print("Both clients matched the Java opening and closing ticks, two-viewer hold, three moving parts and four sound cues.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path, default=ROOT / ".local/create.hmod")
    parser.add_argument("--screenshots", type=Path)
    options = parser.parse_args()
    if options.screenshots:
        options.screenshots = options.screenshots.resolve()
        options.screenshots.mkdir(parents=True, exist_ok=True)
    run(options)
