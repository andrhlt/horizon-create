#!/usr/bin/env python3
"""Replay original sail placement assistance with real mouse and inventory input."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

ORIGIN = (8, 180, 23)
ADJACENT = {
    "down": (8, 179, 23),
    "up": (8, 181, 23),
    "north": (8, 180, 22),
    "south": (8, 180, 24),
    "west": (7, 180, 23),
    "east": (9, 180, 23),
}
SAIL_ITEMS = ("create:white_sail", "create:sail_frame")


def pos(coords):
    return " ".join(map(str, coords))


def setup(control, case):
    control.commands((
        "/fill 5 178 20 12 184 27 minecraft:air",
        "/fill 5 178 20 12 178 27 minecraft:smooth_stone",
        "/clear @s",
    ))
    facing = "north" if case == 6 else "up" if case == 7 else "east"
    name = "red_sail" if case == 4 else "sail_frame" if case == 5 else "white_sail"
    control.command(f"/setblock {pos(ORIGIN)} create:{name}[facing={facing}]")
    if case == 1:
        control.command(f"/setblock {pos(ADJACENT['up'])} minecraft:stone")
    if case == 2:
        control.commands(f"/setblock {pos(ADJACENT[side])} minecraft:stone"
                         for side in ("down", "up", "north", "south"))
    if case == 5:
        control.command(f"/setblock {pos(ADJACENT['up'])} minecraft:water")
    item = SAIL_ITEMS[case == 4]
    control.command(f"/item replace entity @s hotbar.0 with {item} 2")
    if case == 6:
        control.command("/tp @s 8.75 179.0 21.25")
        hit = (8.82, 180.69, 23.375)
    elif case == 7:
        control.command("/setblock 8 181 24 minecraft:stone")
        control.command("/tp @s 8.27 182.0 24.4")
        hit = (8.27, 180.625, 23.63)
    else:
        control.command("/tp @s 6.25 179.0 23.7")
        hit = (8.375, 180.82, 23.69)
    control.call("wait", 4)
    control.call("select", item)
    if case == 3:
        control.call("key", "shift", "down")
        control.call("wait", 3)
    control.call("look-at", *hit)
    control.call("wait", 2)
    return item


def run(args):
    with (ROOT / "fixtures/sail-placement-java.csv").open() as source:
        java = list(csv.DictReader(source))
    with fixture_world(args, "Sail-placement", render=True, pack=args.pack) as control:
        control.command("/gamemode survival")
        for row in java:
            case = int(row["case"])
            item = setup(control, case)
            control.call("mouse", "right", "click")
            control.call("wait", 3)
            if case == 3:
                control.call("key", "shift", "up")
            expected = dict(cell.split("=", 1) for cell in row["neighbors"].split("|") if cell)
            actual = {}
            for side, coords in ADJACENT.items():
                state = control.call("block", *coords)["state"]
                if state.startswith(SAIL_ITEMS):
                    actual[side] = state.replace("[facing=", "[")
            held = control.call("inventory")["counts"].get(item, 0)
            if actual != expected or held != int(row["held"]):
                raise RuntimeError(
                    f"Sail placement {case}: Java {expected}, {row['held']} held; "
                    f"Horizon {actual}, {held} held."
                )
    print(f"All {len(java)} ordinary and assisted sail placements matched Java block states and item use.")


def run_lan(args):
    multiplayer = import_module("test-multiplayer")
    guest_name = "SailGuest"
    with fixture_world(args, "Sail-placement-LAN", render=True, pack=args.pack) as host:
        host.command("/gamemode survival")
        item = setup(host, 0)
        host.call("mouse", "right", "click")
        placed = f"{item}[facing=east]"
        multiplayer.until("the host to place a sail at its upper edge", lambda: (
            host.call("block", *ADJACENT["up"])["state"] == placed
        ))
        host.command("/tp @s 10.5 179 25.5")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-sail-placement-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, guest_name, render=True,
            scenario="sail-placement-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to finish joining", lambda: any(
                player["name"] == guest_name and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            frame = SAIL_ITEMS[1]
            host.commands((
                f"/gamemode survival {guest_name}",
                f"/tp {guest_name} 6.25 179 23.7",
                f"/item replace entity {guest_name} hotbar.0 with {frame} 2",
            ))
            multiplayer.until("the guest to arrive with the frames", lambda: (
                guest.call("inventory")["counts"].get(frame, 0) == 2
                and guest.call("state")["player"]["position"] == [6.25, 179.0, 23.7]
            ))
            guest.call("select", frame)
            guest.call("look-at", 8.375, 180.82, 23.69)
            guest.call("wait", 3)
            guest.call("mouse", "right", "click")
            multiplayer.until("the guest to extend the south edge on both clients", lambda: (
                all(client.call("block", *ADJACENT["south"])["state"] == f"{frame}[facing=east]"
                    for client in (host, guest))
                and guest.call("inventory")["counts"].get(frame, 0) == 1
            ))
    print("The host placed a sail above and the guest extended the other edge with one frame.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    (run_lan if args.lan else run)(args)
