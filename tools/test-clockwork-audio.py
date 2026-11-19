#!/usr/bin/env python3
"""Compare Clockwork hand audio in real Horizon host and guest clients."""

import argparse
from collections import Counter
import csv
from importlib import import_module
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

removal = import_module("test-clockwork-removal")
clockwork = import_module("test-clockwork-bearing")
multiplayer = import_module("test-multiplayer")
windmill = import_module("test-windmill")
CUES = {
    "create:contraption_assemble", "create:contraption_assemble_compounded_1",
    "create:contraption_disassemble",
}


def normalize(ident, source, x, y, z, gain, pitch):
    category = "block" if source == "4" else source
    return (ident, category, float(x), float(y), float(z), round(float(gain), 4), round(float(pitch), 4))


def playback(client):
    log = client.socket.parent / "ctl.log"
    events = []
    for line in log.read_text().splitlines():
        if "CREATE_ELEVATOR_PLAYBACK " not in line:
            continue
        fields = line.split("CREATE_ELEVATOR_PLAYBACK ", 1)[1].split(",")
        if fields[0] in CUES:
            events.append(normalize(*fields))
    return Counter(events)


def expected():
    with (ROOT / "fixtures/clockwork-audio-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    if {int(row["tick"]) for row in rows} != {6}:
        raise RuntimeError("Clockwork audio fixture does not identify the action tick.")
    events = Counter()
    for row in rows:
        center = removal.RIGS[int(row["rig"])]
        coords = (float(row[axis]) + base for axis, base in zip("xyz", center, strict=True))
        events[normalize(row["id"], row["category"], *coords, row["gain"], row["pitch"])] += 1
    return events


def run(args):
    os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    reference = expected()
    name = "ClockListener"
    with fixture_world(args, "Clockwork-audio", render=True, pack=args.pack) as host:
        removal.setup(host)
        host.command("/tp @s 12.5 180 33.5")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-clockwork-audio-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, name, render=True, scenario="clockwork-audio-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the Clockwork listener to join", lambda: any(
                player["name"] == name and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.command(f"/tp {name} 12.5 180 33.5")
            multiplayer.until("the Clockwork listener to reach the rigs", lambda: (
                guest.call("state")["player"]["position"] == [12.5, 180.0, 33.5]
            ))
            start = host.clock()
            for tick in range(1, 7):
                host.step_to(start + tick)
                if tick == 1:
                    for rig in range(3):
                        _, motor, face, _ = removal.geometry(rig)
                        host.command(f"/setblock {windmill.coords(motor)} create:creative_motor[facing={face}]")
            for client in (host, guest):
                if playback(client):
                    raise RuntimeError("Horizon played a Clockwork contraption sound before Java's stop tick.")
            removal.action(host, obstruction=False)
            multiplayer.until("both clients to start all six Clockwork cues", lambda: (
                sum(playback(host).values()) >= sum(reference.values())
                and sum(playback(guest).values()) >= sum(reference.values())
            ))
            for role, client in (("host", host), ("guest", guest)):
                heard = playback(client)
                if heard != reference:
                    raise RuntimeError(f"Clockwork {role} sound differs from Java: expected {reference}, got {heard}.")
            if host.clock() != start + 6:
                raise RuntimeError("Clockwork started its stop cues outside the original tick.")
    print("Host and guest matched all six Java Clockwork stop cues, including tick, position, volume and pitch.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda value: Path(value).resolve(strict=True))
    run(parser.parse_args())
