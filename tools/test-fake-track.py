#!/usr/bin/env python3
"""Exercise curve markers, owner removal, and random-tick expiry headlessly."""

import argparse
import csv
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

spec = importlib.util.spec_from_file_location("track_curve", ROOT / "tools/test-track-curve.py")
track_curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(track_curve)
mp_spec = importlib.util.spec_from_file_location("multiplayer", ROOT / "tools/test-multiplayer.py")
multiplayer = importlib.util.module_from_spec(mp_spec)
mp_spec.loader.exec_module(multiplayer)


def markers(control):
    positions = [(x, 112, z) for x in range(7, 16) for z in range(-8, 1)]
    replies = control.commands(
        f"/execute if block {x} {y} {z} create:fake_track"
        for x, y, z in positions
    )
    return {pos for pos, reply in zip(positions, replies) if reply.startswith("Test passed")}


def step(control, ticks):
    control.command(f"/tick step {ticks}")
    control.call("wait", ticks + 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    with (ROOT / "fixtures/track_curve-java.csv").open() as file:
        case = next(csv.DictReader(file))
    with fixture_world(args, "Fake-track", track_curve.STRUCTURE, pack=args.pack) as control:
        control.command("/fill -11 111 -24 25 111 7 minecraft:smooth_stone")
        control.command("/gamemode survival")
        control.command("/attribute @s minecraft:gravity base set 0")
        track_curve.test_case(control, case)
        placed = markers(control)
        if not placed:
            raise RuntimeError("Creating the curve did not place any Fake Track markers")
        first = set(placed)
        second_case = dict(case)
        track_curve.test_case(control, second_case, offset=(-1, 0, -1), reset=False, validate=False)
        second = set(markers(control))
        shared = first & second
        if not shared:
            raise RuntimeError(f"Offset curve pair had no shared markers: first={sorted(first)}, second={sorted(second)}")
        if not (second - first):
            raise RuntimeError("Offset curve pair had no exclusive markers")
        control.command("/tick freeze")
        network = control.call("lan", "open", "0", "commands", "force")
        with TemporaryDirectory(prefix="hc-fake-track-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{network['port']}", "FakeTrackGuest", scenario="fake-track", pack=args.pack,
        ) as guest:
            multiplayer.until("the Fake Track guest to join", lambda: any(
                p["name"] == "FakeTrackGuest" and p["placed"] for p in control.call("lan", "status")["guests"]
            ))
            control.command("/tp FakeTrackGuest 11.5 112 -6.5")
            guest.call("wait", 5)
            authoritative = {
                pos for pos in first | second
                if control.call("block", *pos)["state"] == "create:fake_track"
            }
            missing = [pos for pos in authoritative if guest.call("block", *pos)["state"] != "create:fake_track"]
            if missing:
                for pos in missing:
                    neighbors = [(pos[0] + dx, pos[1] + dy, pos[2] + dz)
                                 for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0),
                                                    (0, -1, 0), (0, 0, 1), (0, 0, -1))]
                    print("LAN diagnostic", pos,
                          "host", control.call("block", *pos),
                          "guest", guest.call("block", *pos),
                          "host_neighbors", [control.call("block", *p)["state"] for p in neighbors],
                          "guest_neighbors", [guest.call("block", *p)["state"] for p in neighbors],
                          flush=True)
                raise RuntimeError(f"Guest missing markers after explicit sync: {missing}")
        control.command("/tick unfreeze")
        control.command("/setblock 6 112 -9 minecraft:air")
        step(control, 1)
        remaining = markers(control)
        if not shared <= remaining:
            raise RuntimeError(f"Removing one curve deleted shared markers: {sorted(shared - remaining)}")
        control.command("/setblock 7 112 -8 minecraft:air")
        step(control, 1)
        if markers(control):
            raise RuntimeError("Removing the final curve owner left Fake Track markers")
        track_curve.test_case(control, case)
        placed = markers(control)
        if not placed:
            raise RuntimeError("Recreating the curve did not place markers")
        control.command("/save-all flush")
        control.restart()
        if markers(control) != placed:
            raise RuntimeError("Saved curve did not retain its Fake Track markers after reopen")
        step(control, 120)
        if markers(control) != placed:
            raise RuntimeError("The live curve did not keep its markers alive")
        control.command("/gamemode creative")
        control.command("/tp @s 5.5 112 -7.5")
        control.call("look-at", 7.5, 112.06, -7.5)
        control.call("mouse", "left", "click")
        step(control, 1)
        remaining = markers(control)
        failures = []
        owner = control.call("block", 7, 112, -8)["state"]
        if owner != "minecraft:air":
            failures.append(f"Physical break did not remove the owner: {owner}")
        elif remaining:
            failures.append(f"Physical break left markers behind: {sorted(remaining)}")
        control.command("/gamemode survival")
        track_curve.test_case(control, case)
        control.command("/setblock 7 112 -8 minecraft:air")
        step(control, 1)
        remaining = markers(control)
        if remaining:
            failures.append(f"Command removal left markers behind: {sorted(remaining)}")
        control.command("/setblock 0 115 0 create:fake_track")
        control.command("/setblock 8 115 0 create:fake_track[waterlogged=true]")
        control.command("/gamerule random_tick_speed 4096")
        step(control, 100)
        state = control.call("block", 0, 115, 0)["state"]
        if state != "minecraft:air":
            failures.append(f"An unrefreshed marker did not expire: {state}")
        wet = control.call("block", 8, 115, 0)["state"]
        if not wet.startswith("minecraft:water"):
            failures.append(f"An expired waterlogged marker did not restore water: {wet}")
        if failures:
            raise RuntimeError("; ".join(failures))
    print("Curve marker placement, refresh, removal and random-tick expiry passed.")


if __name__ == "__main__":
    main()
