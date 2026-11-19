#!/usr/bin/env python3
"""Replay adding, editing, removing and reloading ordered Java destinations."""

import argparse
import json
from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

ENTRY = run_path(str(ROOT / "tools/test-train-schedule-entry.py"))
BLANK = run_path(str(ROOT / "tools/test-train-schedule.py"))
MULTIPLAYER = run_path(str(ROOT / "tools/test-multiplayer.py"))
GUEST = "MultiGuest"


def destinations(tag):
    return [entry["Instruction"]["Data"]["Text"] for entry in tag["Entries"]]


def fill_field(control, new_filter, existing=""):
    control.call("wait", 3)
    control.call("click-button", "Station Name")
    if existing:
        control.call("script", script="key backspace tap\n" * len(existing))
    control.call("type", new_filter)
    control.call("click-button", "Confirm Action")
    control.call("wait", 3)


def click_add(control, label):
    control.call("click-button", "Add Action")
    fill_field(control, label)


def assert_rows(control, tag):
    labels = list(ENTRY["buttons"](control))
    expect = destinations(tag)
    rows = [label for label in labels if label in expect]
    if rows != expect:
        raise RuntimeError(f"Expected ordered rows {expect}, found {rows}.")


def close(control):
    control.call("click-button", "Done")
    control.call("wait", 8)
    if control.call("state")["screen"] != "playing":
        raise RuntimeError("Done did not close the Schedule.")


def verify_loop(control, path, expected, ffmpeg):
    actual = BLANK["loop_green"](control, ENTRY["buttons"](control), path, ffmpeg)
    if actual != bool(expected["Cyclic"]):
        raise RuntimeError(f"Loop Forever's visible state differed: {actual}.")


def exercise(control, authority, actor, references, scratch, args, *, render_loop=False):
    first, second = destinations(references["TWO"])
    edited = destinations(references["REOPEN_TWO"])[1]
    ENTRY["use"](control)
    click_add(control, first)
    click_add(control, second)
    assert_rows(control, references["TWO"])
    if render_loop:
        verify_loop(control, ROOT / ".local/train-schedule-two.png", references["TWO"], args.ffmpeg)

    control.call("click-button", "Loop Forever")
    control.call("click-button", second)
    fill_field(control, edited, second)
    assert_rows(control, references["EDIT"])
    close(control)
    expected = references["REOPEN_TWO"]
    MULTIPLAYER["until"]("both edited destination compounds", lambda: ENTRY["selected_schedule"](authority, actor) == expected)
    MULTIPLAYER["until"]("the client to display its exact two-entry item", lambda: ENTRY["client_schedule"](control) == expected)

    ENTRY["use"](control)
    assert_rows(control, expected)
    if render_loop:
        verify_loop(control, scratch / "loop-reopened.png", expected, args.ffmpeg)
    control.call("click-button", "Remove Action 1")
    control.call("wait", 3)
    assert_rows(control, references["DELETE"])
    if first in ENTRY["buttons"](control):
        raise RuntimeError("Removing the first action left its row behind.")
    close(control)
    expected = references["REOPEN_DELETE"]
    MULTIPLAYER["until"]("the exact remaining action on the server", lambda: ENTRY["selected_schedule"](authority, actor) == expected)
    MULTIPLAYER["until"]("the remaining action in the client inventory", lambda: ENTRY["client_schedule"](control) == expected)
    ENTRY["use"](control)
    assert_rows(control, expected)
    if render_loop:
        verify_loop(control, scratch / "loop-after-delete.png", expected, args.ffmpeg)
    close(control)


def run(args):
    references = json.loads((ROOT / "fixtures/train-schedule-multi-java.json").read_text())
    with TemporaryDirectory(prefix="hc-schedule-multi-") as scratch, fixture_world(
        args, "train-schedule-multi", render=True, pack=args.pack,
    ) as host:
        scratch = Path(scratch)
        host.commands((
            "/fill 5 95 37 12 95 46 minecraft:smooth_stone",
            "/tp @s 8.5 96 43.3 180 -30",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:schedule",
        ))
        host.call("options-set", "guiScale", "2")
        host.call("select", "create:schedule")
        exercise(host, host, "@s", references, scratch, args, render_loop=True)
        network = host.call("lan", "open", "0", "commands", "force")
        with MULTIPLAYER["joined_client"](
            args, scratch, f"127.0.0.1:{network['port']}", GUEST, render=True,
            scenario="train-schedule-multi", pack=args.pack,
        ) as guest:
            MULTIPLAYER["until"]("the two-entry guest to enter", lambda: any(
                player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/tp {GUEST} 9.5 96 43.3 180 -30",
                f"/gamemode survival {GUEST}",
                f"/item replace entity {GUEST} hotbar.0 with create:schedule",
            ))
            MULTIPLAYER["until"]("a blank guest schedule", lambda: guest.call("inventory")["counts"].get("create:schedule") == 1)
            guest.call("select", "create:schedule")
            exercise(guest, host, GUEST, references, scratch, args)

        host.restart()
        if ENTRY["selected_schedule"](host, "@s") != references["REOPEN_DELETE"]:
            raise RuntimeError("Removing one destination did not persist after restarting the host.")
    print("Solo and LAN matched Java's ordered two destinations, editing the second, deleting the first, and keeping Loop Forever off after reopening and restart.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    run(parser.parse_args())
