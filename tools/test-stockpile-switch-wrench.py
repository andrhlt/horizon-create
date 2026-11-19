#!/usr/bin/env python3
"""Replay original Stockpile Switch wrench rotations, sampling and pickup."""

import argparse
from contextlib import contextmanager
import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


ITEM = "create:stockpile_switch"
WRENCH = "create:wrench"
POSITION = (8, 102, -9)
GUEST = "StockpileWrench"
FACES = {
    "north": (0, 0, -1),
    "south": (0, 0, 1),
    "east": (1, 0, 0),
    "west": (-1, 0, 0),
    "up": (0, 1, 0),
    "down": (0, -1, 0),
}
spec = spec_from_file_location("editor", ROOT / "tools/test-stockpile-switch-editor.py")
editor = module_from_spec(spec)
spec.loader.exec_module(editor)


def entries(kind):
    with (ROOT / f"fixtures/stockpile-switch-wrench-{kind}-java.csv").open(newline="") as source:
        return list(csv.reader(source))


def state(facing, mount, level=0, power=False):
    energized = str(power).lower()
    return f"{ITEM}[facing={facing},target={mount},level={level},powered={energized}]"


def arena(control):
    control.commands((
        "/fill 4 101 -14 14 108 -4 minecraft:air",
        "/fill 4 100 -14 14 100 -4 minecraft:smooth_stone",
        "/setblock 10 103 -9 minecraft:smooth_stone",
        "/setblock 10 100 -9 minecraft:air",
        "/setblock 10 99 -9 minecraft:smooth_stone",
    ))


def stand(host, actor, name, face):
    x, y, z = POSITION
    dx, dy, dz = FACES[face]
    if dy == 1:
        feet = (10.5, 104, -8.5)
    elif dy == -1:
        feet = (10.5, 100, -8.5)
    else:
        feet = (x + .5 + dx * 2, y - 1, z + .5 + dz * 2)
    host.command(f"/tp {name} {editor.xyz(feet)}")
    editor.wait_for(actor, "the wrench to reach the selected face", lambda:
        tuple(actor.call("state")["player"]["position"][:3]) == feet
    )


def equip(host, actor, name):
    host.commands((f"/gamemode survival {name}", f"/item replace entity {name} hotbar.0 with {WRENCH}"))
    editor.wait_for(actor, "the wrench item", lambda: actor.call("inventory")["counts"].get(WRENCH) == 1)
    actor.call("select", WRENCH)


def verify_poses(args):
    expected = entries("poses")
    assert len(expected) == 36
    with fixture_world(args, "StockpileWrenchPoses", render=True, pack=args.pack) as control:
        arena(control)
        equip(control, control, "@s")
        for target, click, facing, next_facing, next_mount in expected:
            before_mount = {"up": "ceiling", "down": "floor"}.get(target, "wall")
            control.commands((
                f"/setblock {editor.xyz(POSITION)} minecraft:air",
                f"/setblock {editor.xyz(POSITION)} {state(facing, before_mount)}",
            ))
            stand(control, control, "@s", click)
            control.call("interact", *POSITION, click)
            check = f"/execute if block {editor.xyz(POSITION)} {state(next_facing, next_mount)}"
            result = control.command(check)
            assert result.startswith("Test passed"), (target, click, next_facing, next_mount, control.call("block", *POSITION))
    print("All 36 original Wrench direction pairs matched, including wall, floor and ceiling targets.")


@contextmanager
def control_actor(host, args, scratch):
    if scratch is None:
        yield host, "@s"
        return
    multiplayer = editor.load_multiplayer()
    host.command("/tp @s 12.5 101 -8.5")
    address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
    with multiplayer.joined_client(
        args, scratch, address, GUEST, render=True, scenario="stockpile-wrench", pack=args.pack,
    ) as guest:
        multiplayer.until("the wrench guest to join", lambda: any(
            player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]
        ))
        yield guest, GUEST


def setup(host):
    arena(host)
    # This action sequence approaches from the east and never uses the underside opening.
    host.command("/setblock 10 100 -9 minecraft:smooth_stone")
    source = (((8, 102, -8), 64), ((7, 102, -9), 32), ((8, 101, -9), 96))
    for position, amount in source:
        xy = editor.xyz(position)
        host.commands((
            f"/setblock {xy} minecraft:barrel",
            f"/item replace block {xy} container.0 with minecraft:stone {min(64, amount)}",
        ))
        if amount > 64:
            host.command(f"/item replace block {xy} container.1 with minecraft:stone {amount - 64}")
    host.commands((
        f"/setblock {editor.xyz(POSITION)} {state('south', 'wall')}",
        f"/data merge block {editor.xyz(POSITION)} {{OffBelowAmount:32.0f,OnAboveAmount:64.0f}}",
    ))


def verify_time(args, scratch):
    expected = entries("ticks")
    assert len(expected) == 26
    acts = {4: "up", 10: "north", 18: "east", 23: "east"}
    with fixture_world(args, "StockpileWrenchTicks", render=True, pack=args.pack) as host:
        setup(host)
        with control_actor(host, args, scratch) as (actor, name):
            equip(host, actor, name)
            start = host.clock()
            for tick, row in enumerate(expected[1:], 1):
                host.step_to(start + tick)
                if tick in acts:
                    face = acts[tick]
                    stand(host, actor, name, face)
                    if tick == 23:
                        actor.call("key", "shift", "down")
                        actor.call("wait", 3)
                    try:
                        actor.call("interact", *POSITION, face)
                    finally:
                        if tick == 23:
                            actor.call("key", "shift", "up")
                tick_id, facing, mount, amount, raw, powered, level, pickup = row
                assert int(tick_id) == tick
                expected_state = "minecraft:air" if mount == "-" else state(facing, mount, int(level), powered == "true")
                query = f"/execute if block {editor.xyz(POSITION)} {expected_state}"
                result = host.command(query)
                assert result.startswith("Test passed"), (tick, query, host.call("block", *POSITION), result)
                if mount != "-":
                    data = host.command(f"/data get block {editor.xyz(POSITION)}")
                    actual = tuple(editor.field(data, key) for key in (
                        "CurrentAmount", "Powered", "PoweredAfterDelay", "OffBelowAmount", "OnAboveAmount",
                    ))
                    target = (int(amount), int(raw == "true"), int(powered == "true"), 32, 64)
                    assert actual == target, (tick, target, data)
                assert actor.call("inventory")["counts"].get(ITEM, 0) == int(pickup), (tick, pickup)
    who = "Guest" if scratch else "Host"
    print(f"{who} matched all 25 original action and sampling ticks, including delayed mount updates and survival pickup.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--poses", action="store_true")
    modes.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.poses:
        verify_poses(args)
    elif args.lan:
        with TemporaryDirectory(prefix="hc-stwr-") as scratch:
            verify_time(args, Path(scratch))
    else:
        verify_time(args, None)


if __name__ == "__main__":
    main()
