#!/usr/bin/env python3
"""Replay the Java Clockwork Bearing arrangement board locally and over LAN."""

import argparse
import csv
from pathlib import Path
import re
from runpy import run_path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

BEARING = (8, 201, 42)
GUEST = "ClockworkGuest"
TRACE = "CREATE_SPEED_CONTROLLER_INPUT"


def mode(control):
    data = control.command("/data get block 8 201 42 ScrollValue")
    match = re.search(r"block data: (\d+)$", data)
    if not match:
        raise RuntimeError(f"Clockwork mode did not serialize: {data}")
    return int(match[1])


def aim(control):
    control.call("look-at", 8.375, 201.5, 42.985)
    control.call("wait", 2)


def open_board(control, labels, warmup, spacing):
    aim(control)
    control.call("mouse", "right", "down")
    control.call("wait", warmup + 1)
    screen = control.call("screen")
    buttons = screen["buttons"]
    if control.call("state")["screen"] != "mod" or [cell["label"] for cell in buttons] != labels:
        raise RuntimeError(f"Expected the original ordered Clockwork options {labels}: {screen}")
    cells = [(cell["x"] + cell["w"] / 2, cell["y"] + cell["h"] / 2) for cell in buttons]
    if tuple(cells[i + 1][0] - cells[i][0] for i in range(2)) != spacing or len({y for _, y in cells}) != 1:
        raise RuntimeError(f"Clockwork option spacing differed from Java: {cells}")
    return cells


def release(control, pointer):
    control.call("click-at", *pointer, "right")
    control.call("wait", 3)
    if control.call("state")["screen"] != "playing":
        raise RuntimeError("Clockwork setting did not close on release")


def holds(log, expected, warmup):
    last_hold = None
    events = {"open": 0, "release": 0, "submit": 0}
    for row in log.read_text().splitlines():
        if not row.startswith(TRACE + " "):
            continue
        _, tick, event, position = row.split()
        if position != ",".join(map(str, BEARING)):
            continue
        tick = int(tick)
        if event == "hold":
            last_hold = tick
        elif event in events:
            events[event] += 1
            if event == "open" and (last_hold is None or tick - last_hold + 1 != warmup):
                raise RuntimeError(f"Clockwork board did not open after {warmup} client ticks: {row}")
    if any(count != expected for count in events.values()):
        raise RuntimeError(f"Expected {expected} Clockwork board opens, releases and submissions: {events}")


def run(args):
    with (ROOT / "fixtures/clockwork-settings-java.csv").open() as file:
        expected = list(csv.DictReader(file))
    first = expected[0]
    labels = [first[f"option{index}"] for index in range(3)]
    warmup = int(first["held_ticks"])
    spacing = (float(first["first_interval"]), float(first["second_interval"]))
    multiplayer = run_path(str(ROOT / "tools/test-multiplayer.py"))
    until = multiplayer["until"]
    with fixture_world(args, "clockwork-settings", render=True, pack=args.pack, env={TRACE + "_TRACE": "1"}) as host:
        host.commands((
            "/fill 6 200 40 11 200 47 minecraft:smooth_stone",
            "/setblock 8 201 42 create:clockwork_bearing[facing=east]",
            "/tp @s 8.375 201 45.5 180 24",
            "/gamemode survival",
        ))
        host.step_to(host.clock() + 1)
        default = mode(host)
        aim(host)
        host.call("script", script="mouse right down\nwait 2\nmouse right up\nwait 6\n")
        if host.call("state")["screen"] != "playing" or mode(host) != default:
            raise RuntimeError("A two-tick use changed Clockwork mode or opened its board")

        for row in expected:
            before, selected = int(row["initial"]), int(row["confirmed"])
            if mode(host) != before:
                raise RuntimeError(f"Clockwork failed to retain arrangement {before}")
            cells = open_board(host, labels, warmup, spacing)
            host.call("scroll-at", *cells[selected], 0)
            if before == 1:
                host.call("click-at", *cells[selected])
                host.call("wait", 2)
                if host.call("state")["screen"] != "mod" or mode(host) != before:
                    raise RuntimeError("Left click committed the Clockwork setting")
            host.call("screenshot", ROOT / f".local/clockwork-settings-mode-{selected}.png")
            release(host, cells[selected])
            if mode(host) != selected:
                raise RuntimeError(f"Clockwork right release did not commit option {selected}")

        host.call("options-set", "lang", "de_de")
        german = ["Stundenzeiger zuerst", "Minutenzeiger zuerst", "24-Stunden-Zeiger zuerst"]
        cells = open_board(host, german, warmup, spacing)
        host.call("screenshot", ROOT / ".local/clockwork-settings-german.png")
        release(host, cells[0])
        host.call("options-set", "lang", "en_us")
        if mode(host) != 0:
            raise RuntimeError("An unchanged Clockwork selection changed the saved mode")

        holds(host.socket.parent / "ctl.log", len(expected) + 1, warmup)
        host.command("/tp @s 6.5 201 45.5")
        network = host.call("lan", "open", "0", "commands", "force")
        with TemporaryDirectory(prefix="hccw-") as scratch, multiplayer["joined_client"](
            args, Path(scratch), f"127.0.0.1:{network['port']}", GUEST,
            render=True, scenario="clockwork-settings", pack=args.pack,
        ) as guest:
            until("the Clockwork guest to enter", lambda: any(
                player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} 8.375 201 45.5 180 24",
            ))
            host.step_to(host.clock() + 1)
            until("the guest to see Clockwork", lambda: guest.call("block", *BEARING)["block"] == "create:clockwork_bearing")
            cells = open_board(guest, labels, warmup, spacing)
            release(guest, cells[2])
            until("the guest's arrangement to reach the host", lambda: mode(host) == 2)
            cells = open_board(guest, labels, warmup, spacing)
            guest.call("screenshot", ROOT / ".local/clockwork-settings-guest-reopen.png")
            release(guest, cells[1])
            until("the guest's second arrangement to reach the host", lambda: mode(host) == 1)
    print("Clockwork English and German labels, 10 px option spacing, six-tick holds and 0→1→2→0 release sequence matched Java.")
    print("A survival LAN guest changed the authority's arrangement twice using the same board.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
