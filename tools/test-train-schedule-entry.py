#!/usr/bin/env python3
"""Replay the first Travel to Station instruction and its item component."""

import argparse
import json
from pathlib import Path
import re
from runpy import run_path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

SCHEDULE = "create:schedule"
GUEST = "EntryGuest"
COMPONENT = "create:train_schedule"


def buttons(control):
    screen = control.call("screen")
    if screen["screen"] != "mod":
        raise RuntimeError(f"Schedule editor did not open: {screen}")
    return {entry["label"]: entry for entry in screen["buttons"]}


def use(control):
    control.call("mouse", "right", "click")
    control.call("wait", 7)


def snbt(data):
    data = re.sub(r'([,{])\s*([A-Za-z][A-Za-z0-9]*):', r'\1"\2":', data)
    data = re.sub(r'\b(\d+)b(?=\s*[,}])', r'\1', data)
    return json.loads(data)


def selected_schedule(authority, who):
    raw = authority.command(f'/data get entity {who} SelectedItem.components."{COMPONENT}"')
    if "entity data: " not in raw:
        return None
    return snbt(raw.split("entity data: ", 1)[1])


def client_schedule(control):
    slot = control.call("state")["selected"] - 1
    item = next(stack for stack in control.call("inventory")["hotbar"] if stack["slot"] == slot)
    return snbt(item.get("components") or "{}").get(COMPONENT)


def enter_and_close(control, expected, capture=False):
    use(control)
    if not buttons(control)["Add Action"]["enabled"]:
        raise RuntimeError("The blank schedule cannot add its first action.")
    control.call("click-button", "Add Action")
    control.call("wait", 3)
    if not buttons(control)["Station Name"]["enabled"]:
        raise RuntimeError("Add Action did not open the Station Name field.")
    control.call("click-button", "Station Name")
    label = expected["Entries"][0]["Instruction"]["Data"]["Text"]
    control.call("type", label)
    control.call("wait", 2)
    if capture:
        control.call("screenshot", ROOT / ".local/train-schedule-destination-editor.png")
    control.call("click-button", "Confirm Action")
    control.call("wait", 3)
    if label not in buttons(control):
        raise RuntimeError(f"The timetable does not show its Travel to Station card: {buttons(control)}")
    if capture:
        control.call("screenshot", ROOT / ".local/train-schedule-destination-card.png")
    control.call("click-button", "Done")
    control.call("wait", 8)
    if control.call("state")["screen"] != "playing":
        raise RuntimeError("Done did not close the timetable.")


def reopen(control, expected):
    label = expected["Entries"][0]["Instruction"]["Data"]["Text"]
    use(control)
    if label not in buttons(control):
        raise RuntimeError(f"Saved first action did not reappear: {buttons(control)}")
    control.call("click-button", "Done")
    control.call("wait", 7)


def run(args):
    expected = json.loads((ROOT / "fixtures/train-schedule-entry-java.json").read_text())
    multiplayer = run_path(str(ROOT / "tools/test-multiplayer.py"))
    until = multiplayer["until"]
    with fixture_world(args, "train-schedule-entry", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 5 95 37 12 95 46 minecraft:smooth_stone",
            "/tp @s 8.5 96 43.3 180 -30",
            "/gamemode survival",
            f"/item replace entity @s hotbar.0 with {SCHEDULE}",
        ))
        host.call("options-set", "guiScale", "2")
        host.call("select", SCHEDULE)
        enter_and_close(host, expected, capture=True)
        if selected_schedule(host, "@s") != expected:
            raise RuntimeError(f"Host component differs from Java: {selected_schedule(host, '@s')}")
        reopen(host, expected)

        network = host.call("lan", "open", "0", "commands", "force")
        with TemporaryDirectory(prefix="hc-entry-lan-") as scratch, multiplayer["joined_client"](
            args, Path(scratch), f"127.0.0.1:{network['port']}", GUEST, render=True,
            scenario="train-schedule-entry", pack=args.pack,
        ) as guest:
            until("the schedule guest to enter", lambda: any(
                player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/tp {GUEST} 9.5 96 43.3 180 -30",
                f"/gamemode survival {GUEST}",
                f"/item replace entity {GUEST} hotbar.0 with {SCHEDULE}",
            ))
            until("the guest to receive a blank Schedule", lambda: guest.call("inventory")["counts"].get(SCHEDULE) == 1)
            guest.call("select", SCHEDULE)
            enter_and_close(guest, expected)
            until("the guest's exact component to reach the host", lambda: selected_schedule(host, GUEST) == expected)
            until("the exact component to reach the guest inventory", lambda: client_schedule(guest) == expected)
            reopen(guest, expected)

        host.restart()
        if selected_schedule(host, "@s") != expected:
            raise RuntimeError("The first Travel to Station did not survive reopening the world.")
        reopen(host, expected)
    print("Solo host and LAN guest entered and reopened Java's first Travel to Station action and exact five-second delay component.")
    print("The host's component matched after reopening the world.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
