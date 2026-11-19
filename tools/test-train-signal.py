#!/usr/bin/env python3
"""Replay original Train Signal target, paired direction, and powered timing cases."""

import argparse
import csv
from importlib import import_module
from itertools import groupby
from pathlib import Path
from tempfile import TemporaryDirectory
import re

from fixture_world import ROOT, fixture_world

windmill = import_module("test-windmill")
SIGNAL = "create:track_signal"
ORIGIN = (9, 112, -8)
DESTINATIONS = ((9, 112, -5), (9, 112, -11), (5, 112, -5), (13, 112, -5))


def coords(pos):
    return " ".join(map(str, pos))


def at(pos, *delta):
    return tuple(a + b for a, b in zip(pos, delta, strict=True))


def setup(control):
    control.commands((
        "/fill -2 111 -15 25 111 1 minecraft:smooth_stone",
        "/fill 1 112 -8 23 112 -8 create:track[shape=xo]",
        "/gamemode survival",
    ))
    for _ in range(7):
        control.step_to(control.clock() + 1)


def place(control, java):
    for row in java:
        index = int(row["case"])
        x, y, z = ORIGIN
        control.command(f"/item replace entity @s hotbar.0 with {SIGNAL} 2")
        control.call("wait", 2)
        control.call("select", SIGNAL)
        if index != 3:
            side = 1 if index == 1 else -1
            control.command(f"/tp @s {x + 0.5 + side * 2} {y} {z + 0.5} {side * 90} 20")
            control.call("wait", 2)
            control.call("look-at", x + 0.5, y + 0.06, z + 0.5)
            control.call("mouse", "right", "click")
            control.call("wait", 3)
        selected = control.command("/data get entity @s SelectedItem")
        tracked = int("create:track_targeting_item_selected_pos" in selected)
        destination = DESTINATIONS[index]
        a, b, c = destination
        control.command(f"/tp @s {a + .5} {b} {c + 2.5} 180 20")
        control.call("wait", 2)
        control.call("interact", a, b - 1, c, "up")
        control.call("wait", 3)
        remaining = int(windmill.number(control.command("/data get entity @s SelectedItem"), "count"))
        installed = int(control.command(f"/execute if block {coords(destination)} {SIGNAL}").startswith("Test passed"))
        found = (tracked, remaining, installed)
        want = tuple(int(row[key]) for key in ("selected", "held", "placed"))
        if found != want:
            raise RuntimeError(f"Train Signal placement {index}: Horizon {found}, Java {want}.")


def sample(control, tick, index):
    dst = coords(DESTINATIONS[index])
    nbt, cross, power = control.commands((
        f"/data get block {dst}", f"/execute if block {dst} {SIGNAL}[type=cross_signal]",
        f"/execute if block {dst} {SIGNAL}[powered=true]",
    ))
    identifier = lambda key: re.search(rf'{key}: "([A-Z]+)"', nbt)[1]
    linked = re.search(r"TargetTrack: \[I; (-?\d+), (-?\d+), (-?\d+)\]", nbt)
    if linked is None:
        raise RuntimeError(f"Train Signal at {dst} lost its selected track: {nbt}")
    return {
        "tick": tick, "rig": index, "type": "cross_signal" if cross.startswith("Test passed") else "entry_signal",
        "powered": str(power.startswith("Test passed")).lower(),
        "signal_state": identifier("State"), "overlay": identifier("Overlay"),
        "reported_power": str(windmill.number(nbt, "Power") == 1).lower(),
        "target_direction": str(windmill.number(nbt, "TargetDirection") == 1).lower(),
        **dict(zip(("dx", "dy", "dz"), linked.groups(), strict=True)),
    }


def run(args):
    with (ROOT / "fixtures/train-signal-placement-java.csv").open() as source:
        placement = list(csv.DictReader(source))
    with (ROOT / "fixtures/train-signal-state-java.csv").open() as source:
        rows = list(csv.DictReader(source))
    expected_wire = {}
    if args.comparator:
        with (ROOT / "fixtures/train-signal-wire-java.csv").open() as source:
            expected_wire = {int(row["tick"]): int(row["power"]) for row in csv.DictReader(source)}
    mismatches = []
    with fixture_world(args, "Train-signal", render=True, pack=args.pack) as control:
        setup(control)
        start = control.clock()
        for tick, group in groupby(rows, key=lambda row: int(row["tick"])):
            control.step_to(start + tick)
            if tick == 1:
                place(control, placement)
                if args.comparator:
                    control.commands((
                        "/setblock 9 112 -4 minecraft:comparator[facing=north]",
                        "/setblock 9 112 -3 minecraft:redstone_wire",
                    ))
            if tick in (8, 26):
                block = "redstone_block" if tick == 8 else "air"
                control.command(f"/setblock {coords(at(DESTINATIONS[0], 0, 1, 0))} minecraft:{block}")
            if tick == 35:
                control.command("/item replace entity @s hotbar.0 with create:wrench 1")
                x, y, z = DESTINATIONS[0]
                control.command(f"/tp @s {x + 0.5} {y} {z + 2.5}")
                control.call("wait", 3)
                control.call("select", "create:wrench")
                control.call("interact", x, y, z, "up")
                control.call("wait", 3)
            if tick == 40:
                control.command(f"/setblock {coords(ORIGIN)} minecraft:air")
            if tick in expected_wire:
                strength = expected_wire[tick]
                current = control.command(f"/execute if block 9 112 -3 minecraft:redstone_wire[power={strength}]")
                if not current.startswith("Test passed"):
                    actual = control.call("block", 9, 112, -3)["state"]
                    mismatches.append(f"{tick} comparator output: {actual} vs {strength}")
            for row in group:
                actual = sample(control, tick, int(row["rig"]))
                for key, value in actual.items():
                    if str(value) != row[key]:
                        mismatches.append(f"{tick}/{row['rig']} {key}: {value} vs {row[key]}")
    if mismatches:
        raise RuntimeError(f"{len(mismatches)} Train Signal differences. " + "; ".join(mismatches[:24]))
    print(f"Matched {len(placement)} placement cases and {len(rows)} Java Train Signal state samples.")
    if expected_wire:
        print(f"Matched comparator output on all {len(expected_wire)} Java wire ticks.")


def craft(args):
    inventory = import_module("test-survival-crafting")
    with fixture_world(args, "Train-signal-crafting", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 5 179 20 10 179 25 minecraft:smooth_stone",
            "/setblock 8 180 23 minecraft:crafting_table",
            "/tp @s 6.5 180 23.5", "/gamemode survival",
            "/item replace entity @s hotbar.0 with create:railway_casing 1",
            "/item replace entity @s hotbar.1 with create:electron_tube 1",
        ))
        control.call("wait", 3)
        control.call("interact", 8, 180, 23, "west")
        control.call("wait", 3)
        inventory.distribute(control, 0, (101,))
        inventory.distribute(control, 1, (102,))
        inventory.craft(control, SIGNAL, 4)
    print("Survival crafting matched Java's four Train Signals from Railway Casing and an Electron Tube.")


def run_lan(args):
    multiplayer = import_module("test-multiplayer")
    name = "SignalGuest"
    with fixture_world(args, "Train-signal-LAN", render=True, pack=args.pack) as host:
        setup(host)
        with (ROOT / "fixtures/train-signal-placement-java.csv").open() as source:
            place(host, [next(csv.DictReader(source))])
        host.command("/tp @s 11.5 112 -3.5")
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        with TemporaryDirectory(prefix="hc-train-signal-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, name, render=True, scenario="train-signal-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the Signal guest to join", lambda: any(
                player["name"] == name and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            x, y, z = ORIGIN
            host.commands((
                f"/gamemode survival {name}",
                f"/tp {name} {x + 2.5} {y} {z + 0.5} 90 20",
                f"/item replace entity {name} hotbar.0 with {SIGNAL} 2",
                f"/item replace entity {name} hotbar.1 with create:wrench 1",
            ))
            multiplayer.until("the guest and signals to arrive", lambda: (
                guest.call("state")["player"]["position"] == [x + 2.5, float(y), z + 0.5]
                and guest.call("inventory")["counts"].get(SIGNAL, 0) == 2
            ))
            guest.call("select", SIGNAL)
            guest.call("look-at", x + .5, y + .06, z + .5)
            guest.call("mouse", "right", "click")
            multiplayer.until("the guest to select the opposite track side", lambda: (
                "create:track_targeting_item_selected_pos" in host.command(f"/data get entity {name} SelectedItem")
            ))
            a, b, c = DESTINATIONS[1]
            host.command(f"/tp {name} {a + .5} {b} {c + 2.5} 180 20")
            multiplayer.until("the guest to reach their signal support", lambda: (
                guest.call("state")["player"]["position"] == [a + .5, float(b), c + 2.5]
            ))
            guest.call("interact", a, b - 1, c, "up")
            multiplayer.until("both clients to see the guest's signal", lambda: (
                all(client.call("block", a, b, c)["block"] == SIGNAL for client in (host, guest))
                and guest.call("inventory")["counts"].get(SIGNAL, 0) == 1
            ))
            for _ in range(2):
                host.step_to(host.clock() + 1)
            sides = [sample(host, 0, i) for i in range(2)]
            if [row["target_direction"] for row in sides] != ["false", "true"] or sides[1]["overlay"] != "DUAL":
                raise RuntimeError(f"Player actions did not bind opposite sides to one boundary: {sides}.")
            guest.call("select", "create:wrench")
            guest.call("interact", a, b, c, "up")
            guest.call("wait", 4)
            host.step_to(host.clock() + 1)
            multiplayer.until("both clients to see only the guest-facing cross signal", lambda: (
                all("type=cross_signal" in client.call("block", a, b, c)["state"] for client in (host, guest))
            ))
            if sample(host, 0, 0)["type"] != "entry_signal":
                raise RuntimeError("The guest changed the mode on the host's opposite-facing signal.")
    print("Real host and guest bound opposite directions and the guest changed only their side's signal mode.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--comparator", action="store_true")
    mode.add_argument("--lan", action="store_true")
    mode.add_argument("--craft", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    args = parser.parse_args()
    (craft if args.craft else run_lan if args.lan else run)(args)
