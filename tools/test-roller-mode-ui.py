#!/usr/bin/env python3
"""Select all Mechanical Roller modes as a host and LAN guest."""
import argparse
from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

POS = (8, 201, 42)
LABELS = ["Tunnel Pave", "Straight Fill", "Wide Fill"]


def mode(control):
    result = control.command(f"/data get block {' '.join(map(str, POS))} ScrollValue")
    tail = result.rsplit(" ", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def value_box(control):
    facing = control.call("block", *POS)["state"].split("facing=", 1)[1].split(",", 1)[0].split("]", 1)[0]
    offset = {
        "north": (5 / 16, 11 / 16),
        "south": (11 / 16, 5 / 16),
        "west": (15.5 / 16, 5 / 16),
        "east": (0.5 / 16, 11 / 16),
    }[facing]
    return (POS[0] + offset[0], POS[1] + 15.5 / 16, POS[2] + offset[1])


def choose(control, value):
    control.call("look-at", *value_box(control))
    control.call("wait", 2)
    control.call("mouse", "right", "down")
    control.call("wait", 7)
    screen = control.call("screen")
    if control.call("state")["screen"] != "mod":
        raise RuntimeError(f"Mechanical Roller mode board did not open: {screen}")
    buttons = screen["buttons"]
    labels = [button["label"] for button in buttons]
    if labels != LABELS:
        raise RuntimeError(f"Expected Roller modes {LABELS}, got {labels}")
    button = buttons[value]
    control.call("click-at", button["x"] + button["w"] / 2,
                 button["y"] + button["h"] / 2, "right")
    control.call("wait", 3)
    if control.call("state")["screen"] != "playing":
        raise RuntimeError("Confirming a Roller mode did not close the board")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    multiplayer = run_path(str(ROOT / "tools/test-multiplayer.py"))
    until = multiplayer["until"]

    with fixture_world(args, "RollerModeUI", render=True,
                       env={"HORIZON_NO_AUDIO": "1"}) as host:
        host.commands((
            "/fill 6 200 40 11 200 47 minecraft:smooth_stone",
            "/setblock 6 200 42 minecraft:crafting_table",
            "/tp @s 8.3125 201 45.5 180 24",
            "/gamemode survival",
        ))
        host.step_to(host.clock() + 1)
        host.command(f"/setblock {' '.join(map(str, POS))} create:mechanical_roller[facing=north]")
        for selected in (1, 2, 0):
            choose(host, selected)
            if mode(host) != selected:
                raise RuntimeError(f"Host selected mode {selected}, server stored {mode(host)}")

        host.command("/tp @s 6.5 201 45.5")
        network = host.call("lan", "open", "0", "commands", "force")
        with TemporaryDirectory(prefix="roller-mode-ui-") as temp, multiplayer["joined_client"](
            args, Path(temp), f"127.0.0.1:{network['port']}", "RollerGuest",
            render=True, scenario="roller-mode-ui",
        ) as guest:
            until("guest to join", lambda: any(
                player["name"] == "RollerGuest" and player["placed"]
                for player in host.call("lan", "status")["guests"]))
            host.commands((
                "/gamemode survival RollerGuest",
                "/tp RollerGuest 8.3125 201 45.5",
            ))
            host.step_to(host.clock() + 1)
            until("guest to see Roller", lambda:
                  guest.call("block", *POS)["block"] == "create:mechanical_roller")
            choose(guest, 2)
            until("guest mode to reach server", lambda: mode(host) == 2)

        host.command("/save-all flush")
        host.restart()
        if mode(host) != 2:
            raise RuntimeError(f"Roller mode did not persist across reopen: {mode(host)}")

    print("Host selected all three Roller modes; LAN guest selected Wide Fill; mode persisted across reopen.")


if __name__ == "__main__":
    main()
