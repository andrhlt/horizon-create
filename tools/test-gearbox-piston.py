#!/usr/bin/env python3
"""Replay Java's push-only Gearbox transfer and connected shaft restart."""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


BLOCKS = (
    "create:gearbox[axis=y]",
    "create:gearbox[axis=z]",
    "minecraft:stone",
    "minecraft:white_glazed_terracotta",
)
PISTONS = ("sticky_piston", "piston", "sticky_piston", "sticky_piston")


def position(case, ahead=0, dy=0, dz=0):
    return (12 + ahead, 101 + dy, 4 * case - 9 + dz)


def xyz(pos):
    return " ".join(map(str, pos))


SOURCES = (
    (position(0, 2, dz=-1), "south", position(0, 2, dz=1), "z"),
    (position(1, 2, dy=-1), "up", position(1, 2, dy=1), "y"),
)


def rpm(reply):
    speed = re.search(r"\bSpeed: (-?\d+(?:\.\d+)?)", reply)
    return float(speed[1]) if speed else 0.0


def setup(control, cases):
    commands = []
    for case in cases:
        commands.extend((
            f"/setblock {xyz(position(case))} minecraft:{PISTONS[case]}[facing=east]",
            f"/setblock {xyz(position(case, 1))} {BLOCKS[case]}",
        ))
        if case < len(SOURCES):
            motor, facing, shaft, axis = SOURCES[case]
            commands.extend((
                f"/setblock {xyz(motor)} create:creative_motor[facing={facing}]",
                f"/data merge block {xyz(motor)} {{ScrollValue:32}}",
                f"/setblock {xyz(shaft)} create:shaft[axis={axis}]",
            ))
    control.commands(commands)


def reference():
    with (ROOT / "fixtures/gearbox-piston-java.csv").open(newline="") as source:
        records = list(csv.DictReader(source))
    assert len(records) == 104
    return [records[tick:tick + len(BLOCKS)] for tick in range(0, len(records), len(BLOCKS))]


def verify(args):
    cases = range(len(BLOCKS))
    with fixture_world(args, "GearboxPiston", pack=args.pack) as control:
        setup(control, cases)
        start = control.clock()
        for tick, rows in enumerate(reference()):
            if tick:
                control.step_to(start + tick)
            if tick in (5, 15):
                source = "minecraft:redstone_block" if tick == 5 else "minecraft:air"
                control.commands(f"/setblock {xyz(position(case, dy=-1))} {source}" for case in cases)
            expected = []
            for case, row in zip(cases, rows, strict=True):
                assert (int(row["tick"]), int(row["case"])) == (tick, case)
                base = (
                    "minecraft:moving_piston" if row["base"] == "moving"
                    else f"minecraft:{PISTONS[case]}[extended={row['base']}]"
                )
                destination = row["destination"]
                if row["axis"] != "-":
                    destination += f"[axis={row['axis']}]"
                expected.extend(
                    f"/execute if block {xyz(position(case, advance))} {state}"
                    for advance, state in enumerate((base, row["head_pos"], destination))
                )
            replies = control.commands(expected)
            for query, reply in zip(expected, replies, strict=True):
                assert reply.startswith("Test passed"), (tick, query, reply)
            shaft_replies = control.commands(f"/data get block {xyz(shaft)}" for _, _, shaft, _ in SOURCES)
            for case, reply in enumerate(shaft_replies):
                assert rpm(reply) == int(rows[case]["shaft_rpm"]), (tick, case, rows[case], reply)
            for case, row in enumerate(rows):
                if row["axis"] == "-":
                    continue
                reply = control.command(f"/data get block {xyz(position(case, 2))}")
                assert 'id: "create:gearbox"' in reply, (tick, case, reply)
                assert rpm(reply) == int(row["gearbox_rpm"]), (tick, case, row, reply)
    print("All 104 Java Gearbox and vanilla-control piston states matched, including the landing and shaft restart ticks.")


def verify_lan(args, scratch):
    spec = spec_from_file_location("multiplayer", ROOT / "tools/test-multiplayer.py")
    multiplayer = module_from_spec(spec)
    spec.loader.exec_module(multiplayer)
    name = "GearboxPusher"
    lever = (11, 101, -9)
    shaft = SOURCES[0][2]
    with fixture_world(args, "GearboxPistonLAN", render=True, pack=args.pack) as host:
        setup(host, (0,))
        host.commands((
            "/fill 9 100 -10 11 100 -8 minecraft:smooth_stone",
            f"/setblock {xyz(lever)} minecraft:lever[face=floor,facing=east]",
            "/tp @s 17.5 101 -8.5",
        ))
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(
            args, scratch, address, name, render=True, scenario="gearbox-piston", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to join the piston world", lambda: any(
                player["name"] == name and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            host.commands((f"/gamemode survival {name}", f"/tp {name} 9.5 101 -8.5"))
            multiplayer.until("the guest to reach the floor lever", lambda:
                guest.call("state")["player"]["position"][:3] == [9.5, 101.0, -8.5]
            )
            guest.call("look-at", 11.5, 101.16, -8.5)
            guest.call("wait", 3)
            hit = guest.call("looking-at").get("block")
            assert hit and hit["pos"] == list(lever), hit
            for push in (True, False):
                guest.call("mouse", "right", "click")
                setting = "true" if push else "false"
                multiplayer.until("the host to see the guest's lever change", lambda:
                    f"powered={setting}" in host.call("block", *lever)["state"]
                )
                start = host.clock()
                for tick in range(1, 4):
                    host.step_to(start + tick)
                expected_rpm = 0 if push else -32
                shaft_data = host.command(f"/data get block {xyz(shaft)}")
                assert rpm(shaft_data) == expected_rpm, (push, expected_rpm, shaft_data)
                for peer in (host, guest):
                    multiplayer.until("both clients to see the pushed Gearbox axis", lambda:
                        peer.call("block", *position(0, 2))["state"] == BLOCKS[0]
                    )
                if push:
                    host.step_to(start + 4)
                    shaft_data = host.command(f"/data get block {xyz(shaft)}")
                    assert rpm(shaft_data) == -32, shaft_data
                else:
                    multiplayer.until("both clients to see the empty retracted space", lambda: all(
                        peer.call("block", *position(0, 1))["block"] == "minecraft:air" for peer in (host, guest)
                    ))
    print("The guest triggered push and retraction with the floor lever. Both players saw the Gearbox stay on its new axis.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-gbp-") as scratch:
            verify_lan(args, Path(scratch))
    else:
        verify(args)


if __name__ == "__main__":
    main()
