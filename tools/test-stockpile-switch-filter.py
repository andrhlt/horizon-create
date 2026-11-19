#!/usr/bin/env python3
"""Replay Java's Stockpile Switch filter hit areas and immediate stock readings."""

import argparse
from contextlib import contextmanager
import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


POS = ((8, 102, -9), (13, 102, -9))
NAME = "StockpileFilter"
FACES = {
    "north": (0, 0, -1), "south": (0, 0, 1),
    "east": (1, 0, 0), "west": (-1, 0, 0),
    "up": (0, 1, 0), "down": (0, -1, 0),
}
ITEM = "create:stockpile_switch"


def load(name):
    spec = spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


editor = load("test-stockpile-switch-editor")
wrench = load("test-stockpile-switch-wrench")


def entries(kind):
    with (ROOT / f"fixtures/stockpile-switch-filter-{kind}-java.csv").open(newline="") as source:
        return list(csv.reader(source))


def filter_data(data):
    match = re.search(r"\bFilter: \{([^{}]*)\}", data)
    if not match or not match[1]:
        return "-", 0
    values = re.search(r'\bid: "([^"]+)"', match[1])
    count = editor.field(match[1], "count", 1)
    return values[1] if values else "-", count if values else 0


def read(host, pos):
    return host.command(f"/data get block {editor.xyz(pos)}")


def aim(actor, pos, face, center):
    normal = FACES[face]
    surface = .31 if normal[0] else .373
    point = [coordinate + .5 + delta * surface for coordinate, delta in zip(pos, normal, strict=True)]
    if not center:
        if normal[1]:
            point[0] += .24
            point[2] += .20
        else:
            point[1] += .31
    actor.call("look-at", *point)
    actor.call("wait", 3)
    hit = actor.call("looking-at").get("block")
    assert hit and hit["pos"] == list(pos) and hit["face"] == face, (pos, face, center, hit, point)


def equip(host, actor, name, item=None, count=1):
    item = item or "minecraft:air"
    host.command(f"/item replace entity {name} hotbar.0 with {item} {count}")
    if item != "minecraft:air":
        editor.wait_for(actor, "the filter sample to be in hand", lambda:
            actor.call("inventory")["counts"].get(item) == count
        )
        actor.call("select", item)
    else:
        editor.wait_for(actor, "the filter hand to be empty", lambda:
            not actor.call("inventory")["counts"]
        )


def verify_poses(args):
    rows = entries("poses")
    assert len(rows) == 72
    with fixture_world(args, "StockpileFilterPoses", render=True, pack=args.pack) as control:
        wrench.arena(control)
        control.commands((
            "/setblock 10 100 -9 minecraft:smooth_stone",
            "/setblock 10 103 -9 minecraft:air",
            "/setblock 11 103 -9 minecraft:smooth_stone",
            "/setblock 11 100 -9 minecraft:air",
            "/setblock 11 99 -9 minecraft:smooth_stone",
            "/gamemode survival",
        ))
        equip(control, control, "@s", "minecraft:stone", 3)
        pos = POS[0]
        for target, click, center, claimed, count, in_hand in rows:
            mount = {"up": "ceiling", "down": "floor"}.get(target, "wall")
            orientation = "south" if mount != "wall" else target
            control.commands((
                f"/setblock {editor.xyz(pos)} minecraft:air",
                f"/setblock {editor.xyz(pos)} {wrench.state(orientation, mount)}",
            ))
            if click in ("up", "down"):
                height = 104 if click == "up" else 100
                control.command(f"/tp @s 11.5 {height} -8.5")
                control.call("wait", 3)
            else:
                wrench.stand(control, control, "@s", click)
            aim(control, pos, click, center == "true")
            control.call("mouse", "right", "click")
            accepted = claimed == "true"
            future = "playing" if accepted else "mod"
            selected = ("minecraft:stone", int(count)) if accepted else ("-", 0)
            for _ in range(30):
                response = read(control, pos)
                actual_screen = control.call("state")["screen"]
                if filter_data(response) == selected and actual_screen == future:
                    break
                control.call("wait", 2)
            else:
                raise RuntimeError((target, click, center, selected, response, future, actual_screen))
            editor.wait_for(control, "the unchanged stone sample to reconcile", lambda:
                control.call("inventory")["counts"].get("minecraft:stone") == int(in_hand)
            )
            if not accepted:
                editor.confirm(control)
    print("All 72 original face and pointer cases matched, and standard filter samples stayed in hand.")


@contextmanager
def actor_for(host, args, scratch, *, env=None):
    if scratch is None:
        yield host, "@s"
        return
    multiplayer = editor.load_multiplayer()
    host.command("/tp @s 11.0 101 -7.5")
    address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
    with multiplayer.joined_client(
        args, scratch, address, NAME, render=True, scenario="stockpile-filter", pack=args.pack, env=env,
    ) as guest:
        multiplayer.until("the guest to join the filter fixture", lambda: any(
            player["name"] == NAME and player["placed"] for player in host.call("lan", "status")["guests"]
        ))
        yield guest, NAME


def setup(host):
    host.commands((
        "/fill 4 100 -14 15 100 -5 minecraft:smooth_stone",
        "/fill 4 101 -14 15 108 -5 minecraft:air",
        "/setblock 8 102 -8 minecraft:barrel",
        "/item replace block 8 102 -8 container.0 with minecraft:stone 32",
        "/item replace block 8 102 -8 container.1 with minecraft:oak_planks 32",
        "/setblock 13 102 -8 create:fluid_tank",
        '/data merge block 13 102 -8 {TankContent:{Fluid:{id:"minecraft:water",amount:2000}}}',
        *(f"/setblock {editor.xyz(pos)} {wrench.state('south', 'wall')}" for pos in POS),
        "/data merge block 8 102 -9 {OffBelowAmount:16.0f,OnAboveAmount:48.0f}",
        "/data merge block 13 102 -9 {OffBelowAmount:500.0f,OnAboveAmount:1500.0f}",
    ))


def click(host, actor, name, case, tick):
    pos = POS[case]
    x, _, z = pos
    feet = (x + .5, 101, z - 2.5)
    host.command(f"/tp {name} {editor.xyz(feet)}")
    editor.wait_for(actor, "the actor to reach the front filter", lambda:
        tuple(actor.call("state")["player"]["position"][:3]) == feet
    )
    item = None if tick == 13 else (
        ("minecraft:stone" if tick == 4 else "minecraft:iron_ingot") if case == 0
        else ("minecraft:lava_bucket" if tick == 4 else "minecraft:water_bucket")
    )
    count = 3 if item and case == 0 else 1
    equip(host, actor, name, item, count)
    aim(actor, pos, "north", True)
    actor.call("mouse", "right", "click")
    expected = (item, count) if item else ("-", 0)
    editor.wait_for(host, "the filter selection to update on the action tick", lambda:
        filter_data(read(host, pos)) == expected
    )
    assert actor.call("state")["screen"] == "playing"
    if item:
        editor.wait_for(actor, "the sample item's unchanged count to reconcile", lambda:
            actor.call("inventory")["counts"].get(item) == count
        )


def verify_ticks(args, scratch):
    rows = entries("ticks")
    assert len(rows) == 48
    with fixture_world(args, "StockpileFilterTicks", render=True, pack=args.pack) as host:
        setup(host)
        with actor_for(host, args, scratch) as (actor, name):
            host.command(f"/gamemode survival {name}")
            start = host.clock()
            for tick in range(1, 24):
                host.step_to(start + tick)
                if tick in (4, 8, 13):
                    for case in range(len(POS)):
                        click(host, actor, name, case, tick)
                    assert host.clock() == start + tick
                if tick < 4:
                    continue
                for case, pos in enumerate(POS):
                    tick_id, case_id, item, count, amount, raw, output, level = rows[tick * 2 + case]
                    assert (int(tick_id), int(case_id)) == (tick, case)
                    reply = read(host, pos)
                    actual = (
                        filter_data(reply), editor.field(reply, "CurrentAmount"),
                        editor.field(reply, "Powered"), editor.field(reply, "PoweredAfterDelay"),
                    )
                    intended = ((item, int(count)), int(amount), int(raw == "true"), int(output == "true"))
                    assert actual == intended, (tick, case, intended, reply)
                    check = host.command(f"/execute if block {editor.xyz(pos)} {wrench.state('south', 'wall', int(level), output == 'true')}")
                    assert check.startswith("Test passed"), (tick, case, level, host.call("block", *pos))
    who = "Guest" if scratch else "Host"
    print(f"{who} matched 40 Java item/bucket filter observations from the first selection through clearing, with real clicks.")


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
        with TemporaryDirectory(prefix="hc-stf-") as scratch:
            verify_ticks(args, Path(scratch))
    else:
        verify_ticks(args, None)


if __name__ == "__main__":
    main()
