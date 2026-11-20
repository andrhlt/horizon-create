#!/usr/bin/env python3
"""Replay original Smart Observer filter slots and power after real player selection."""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


ID = "create:content_observer"
POS = ((8, 102, -9), (13, 102, -9))
POSE_SAMPLE = "minecraft:iron_ingot"
spec = spec_from_file_location("stockpile_filter", ROOT / "tools/test-stockpile-switch-filter.py")
filters = module_from_spec(spec)
spec.loader.exec_module(filters)
editor = filters.editor
render = filters.load("test-stockpile-switch-filter-render")


def rows(kind):
    with (ROOT / f"fixtures/smart-observer-filter-{kind}-java.csv").open(newline="") as source:
        return list(csv.reader(source))


def state(facing, target, powered="false"):
    return f"{ID}[facing={facing},target={target},powered={powered}]"


def verify_poses(args):
    expected = rows("poses")
    assert len(expected) == 72
    with fixture_world(args, "SmartObserverFilterPoses", render=True, pack=args.pack) as host:
        filters.wrench.arena(host)
        host.commands((
            "/setblock 10 100 -9 minecraft:smooth_stone",
            "/setblock 10 103 -9 minecraft:air",
            "/setblock 11 103 -9 minecraft:smooth_stone",
            "/setblock 11 100 -9 minecraft:air",
            "/setblock 11 99 -9 minecraft:smooth_stone",
            "/gamemode survival",
        ))
        filters.equip(host, host, "@s", POSE_SAMPLE, 3)
        pos = POS[0]
        for observed, click, center, claimed, count, in_hand in expected:
            mount = {"up": "ceiling", "down": "floor"}.get(observed, "wall")
            horizontal = "south" if mount != "wall" else observed
            host.commands((
                f"/setblock {editor.xyz(pos)} minecraft:air",
                f"/setblock {editor.xyz(pos)} {state(horizontal, mount)}",
            ))
            if click in ("up", "down"):
                height = 104 if click == "up" else 100
                host.command(f"/tp @s 11.5 {height} -8.5")
                host.call("wait", 3)
            else:
                filters.wrench.stand(host, host, "@s", click)
            filters.aim(host, pos, click, center == "true")
            host.call("mouse", "right", "click")
            selected = (POSE_SAMPLE, int(count)) if claimed == "true" else ("-", 0)
            if claimed == "true":
                editor.wait_for(host, f"the filter at {observed}/{click}/{center}", lambda:
                    filters.filter_data(filters.read(host, pos)) == selected
                )
            else:
                host.call("wait", 5)
                assert filters.filter_data(filters.read(host, pos)) == selected, (observed, click, center)
            assert host.call("state")["screen"] == "playing"
            assert host.call("inventory")["counts"].get(POSE_SAMPLE) == int(in_hand)
    print("All 72 original Smart Observer face and pointer cases matched with an unchanged sample count.")


def set_filter(host, actor, name, pos, item, count):
    feet = (pos[0] + .5, 101, pos[2] - 2.5)
    host.command(f"/tp {name} {editor.xyz(feet)}")
    editor.wait_for(actor, "the actor to reach the Smart Observer filter", lambda:
        tuple(actor.call("state")["player"]["position"][:3]) == feet
    )
    filters.equip(host, actor, name, item, count)
    filters.aim(actor, pos, "north", True)
    actor.call("mouse", "right", "click")
    selected = (item, count) if item else ("-", 0)
    editor.wait_for(host, f"the filter change at {pos}", lambda:
        filters.filter_data(filters.read(host, pos)) == selected
    )
    assert actor.call("state")["screen"] == "playing"
    if item:
        editor.wait_for(actor, "the ordinary sample to remain in hand", lambda:
            actor.call("inventory")["counts"].get(item) == count
        )


def verify_guest_render(host, guest, start):
    pos = POS[0]
    visible = {face for observed, face, center, active, *_ in rows("poses")
               if observed == "south" and center == active == "true"}
    expected = {key: value for key, value in render.select_expected([(pos, "south")], "minecraft:stone").items()
                if key[2] in visible}
    assert len(expected) == 2
    host.call("look-at", *(coordinate + .5 for coordinate in pos))
    for peer, offset in zip((host, guest), start, strict=True):
        render.render_frames(peer, expected, offset)


def verify_ticks(args, scratch):
    expected = rows("ticks")
    assert len(expected) == 56
    with fixture_world(args, "SmartObserverFilterTicks", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 4 100 -14 15 100 -5 minecraft:smooth_stone",
            "/fill 4 101 -14 15 108 -5 minecraft:air",
            "/setblock 8 102 -8 minecraft:stone",
            "/setblock 13 102 -8 minecraft:barrel",
            "/item replace block 13 102 -8 container.0 with minecraft:stone 32",
            *(f"/setblock {editor.xyz(pos)} {state('south', 'wall')}" for pos in POS),
        ))
        with filters.actor_for(host, args, scratch) as (actor, name):
            host.command(f"/gamemode survival {name}")
            start = host.clock()
            for tick in range(28):
                if tick:
                    host.step_to(start + tick)
                if tick in (4, 9, 13, 22):
                    item = {9: "minecraft:iron_ingot", 22: None}.get(tick, "minecraft:stone")
                    for case, pos in enumerate(POS):
                        if scratch and tick == 4 and case == 0:
                            offsets = [(peer.socket.parent / "ctl.log").stat().st_size
                                       for peer in (host, actor)]
                            set_filter(host, actor, name, pos, item, 3)
                            verify_guest_render(host, actor, offsets)
                        else:
                            set_filter(host, actor, name, pos, item, 3)
                    assert host.clock() == start + tick
                for case, pos in enumerate(POS):
                    tick_id, lane, item, count, wait, powered = expected[tick * 2 + case]
                    assert (int(tick_id), int(lane)) == (tick, case)
                    data = filters.read(host, pos)
                    assert filters.filter_data(data) == (item, int(count)), (tick, case, data)
                    assert editor.field(data, "TurnOff", 0) == int(wait), (tick, case, wait, data)
                    check = host.command(f"/execute if block {editor.xyz(pos)} {state('south', 'wall', powered)}")
                    assert check.startswith("Test passed"), (tick, case, powered, host.call("block", *pos))
    who = "Guest" if scratch else "Host"
    print(f"{who} matched 56 Java Smart Observer filter and power observations across block and inventory targets.")
    if scratch:
        print("Both peers rendered the guest’s sample on the two original Smart Observer faces.")


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
        os.environ[render.ENV] = "1"
        with TemporaryDirectory(prefix="hc-obf-") as scratch:
            verify_ticks(args, Path(scratch))
    else:
        verify_ticks(args, None)


if __name__ == "__main__":
    main()
