#!/usr/bin/env python3
"""Replay the pinned Java Train Schedule's survival recipe and blank editor."""

import argparse
import json
from pathlib import Path
from runpy import run_path
from subprocess import check_output
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

SCHEDULE = "create:schedule"
GUEST = "ScheduleGuest"
LOOP = "Loop Forever"
DONE = "Done"
EXPECTED_WIDGETS = {LOOP: True, "Reset Progress": False, "Skip current Stop": False,
                    "Add Action": True, DONE: True}


def button_map(control):
    screen = control.call("screen")
    if screen["screen"] != "mod":
        raise RuntimeError(f"Train Schedule did not open its editor: {screen}")
    buttons = {button["label"]: button for button in screen["buttons"]}
    if {label: button["enabled"] for label, button in buttons.items()} != EXPECTED_WIDGETS:
        raise RuntimeError(f"Blank Schedule controls differed: {screen}")
    return buttons


def move_away(control, buttons):
    entry = buttons["Add Action"]
    control.call("scroll-at", entry["x"] + 35, entry["y"] + 50, 0)


def loop_green(control, buttons, image, ffmpeg):
    move_away(control, buttons)
    control.call("screenshot", image)
    x, y, w, h = (round(buttons[LOOP][key] * 2) for key in ("x", "y", "w", "h"))
    raw = check_output([str(ffmpeg), "-v", "error", "-i", str(image), "-vf",
                        f"crop={w}:{h}:{x}:{y}", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
    green = sum(g > 90 and g > r * 1.5 and g > b for r, g, b in zip(raw[::3], raw[1::3], raw[2::3], strict=True))
    return green > 20


def use(control):
    control.call("mouse", "right", "click")
    control.call("wait", 8)


def verify_close(control, expected_count, *, authority=None, player="@s"):
    control.call("click-button", DONE)
    control.call("wait", 6)
    if control.call("state")["screen"] != "playing":
        raise RuntimeError("Done did not close the Train Schedule.")
    inventory = control.call("inventory")
    if inventory["counts"].get(SCHEDULE) != expected_count:
        raise RuntimeError(f"Editing consumed or duplicated the blank Schedule: {inventory}")
    item = (authority or control).command(f"/data get entity {player} SelectedItem")
    if SCHEDULE not in item or "train_schedule" in item:
        raise RuntimeError(f"Closing the empty Schedule stored timetable data: {item}")


def run(args):
    reference = json.loads((ROOT / "fixtures/train-schedule-java.json").read_text())
    crafting = run_path(str(ROOT / "tools/test-survival-crafting.py"))
    multiplayer = run_path(str(ROOT / "tools/test-multiplayer.py"))
    until = multiplayer["until"]

    with fixture_world(args, "train-schedule", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 5 95 37 12 95 46 minecraft:smooth_stone",
            "/tp @s 8.5 96 43.3 180 -30",
            "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:sturdy_sheet",
            "/item replace entity @s hotbar.1 with minecraft:paper",
        ))
        host.call("options-set", "guiScale", "2")
        host.call("open-inventory")
        crafting["distribute"](host, 0, (100,))
        crafting["distribute"](host, 1, (101,))
        crafting["craft"](host, SCHEDULE, reference["craft_count"])
        host.call("close")
        host.call("select", SCHEDULE)
        host.call("wait", 3)
        host.call("key", "shift", "down")
        try:
            host.call("wait", 3)
            use(host)
            if (host.call("state")["screen"] == "mod") != reference["sneak_opens"]:
                raise RuntimeError("Crouched use did not match Java.")
        finally:
            host.call("key", "shift", "up")
        host.call("wait", 3)
        use(host)
        buttons = button_map(host)
        if loop_green(host, buttons, ROOT / ".local/train-schedule-empty.png", args.ffmpeg) != reference["loop_default"]:
            raise RuntimeError("The blank editor's Loop Forever state differed from Java.")
        host.call("click-button", LOOP)
        if loop_green(host, buttons, ROOT / ".local/train-schedule-loop-off.png", args.ffmpeg) != reference["loop_toggled"]:
            raise RuntimeError("The Loop Forever toggle did not change the visible state.")
        verify_close(host, reference["close_count"])

        host.call("look-at", 8.5, 95.95, 41.5)
        use(host)
        buttons = button_map(host)
        if loop_green(host, buttons, ROOT / ".local/train-schedule-block-use.png", args.ffmpeg) != reference["block_loop"]:
            raise RuntimeError("Reopening on a block did not restore the original blank loop state.")
        verify_close(host, reference["close_count"])

        network = host.call("lan", "open", "0", "commands", "force")
        with TemporaryDirectory(prefix="hc-schedule-lan-") as scratch, multiplayer["joined_client"](
            args, Path(scratch), f"127.0.0.1:{network['port']}", GUEST, render=True,
            scenario="train-schedule", pack=args.pack,
        ) as guest:
            until("the schedule guest to enter", lambda: any(
                player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/tp {GUEST} 9.5 96 43.3 180 -30",
                f"/gamemode survival {GUEST}",
                f"/item replace entity {GUEST} hotbar.0 with {SCHEDULE}",
            ))
            until("the guest to receive the schedule", lambda: guest.call("inventory")["counts"].get(SCHEDULE) == 1)
            guest.call("select", SCHEDULE)
            use(guest)
            button_map(guest)
            if host.call("state")["screen"] != "playing":
                raise RuntimeError("The guest's Schedule opened on the host.")
            verify_close(guest, 1, authority=host, player=GUEST)
            guest.call("look-at", 9.5, 95.95, 41.5)
            guest.call("interact", 9, 95, 41, "up")
            guest.call("wait", 8)
            button_map(guest)
            verify_close(guest, 1, authority=host, player=GUEST)
    print("Survival crafting, main-hand air and block use, crouch pass, blank loop toggle, and no saved entries matched Java.")
    print("A survival LAN guest opened and closed their own blank Schedule editor.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    run(parser.parse_args())
