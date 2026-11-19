#!/usr/bin/env python3
"""Compare genuine click-targeted Copycat placement assistance with Java Create."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

COPYCAT = import_module("test-copycat")

POS = (8, 170, 24)
PANEL = "create:copycat_panel"
STEP = "create:copycat_step"
DIRECTIONS = {
    "down": (0, -1, 0), "up": (0, 1, 0), "north": (0, 0, -1),
    "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0),
}


def support(control, side, name, distance=1):
    x, y, z = map(lambda pair: pair[0] + pair[1] * distance, zip(POS, DIRECTIONS[side]))
    control.command(f"/setblock {x} {y} {z} {name}")


def setup(control, case, actor='@s'):
    is_step = case.startswith("step")
    wall = case == "panel-up-on-wall"
    upper = case == "step-upper-extend"
    block = STEP if is_step else PANEL
    facing = "south" if is_step else "north" if wall else "up"
    half = (",half=top" if upper else ",half=bottom") if is_step else ""
    control.commands((
        "/fill 6 170 22 12 171 25 minecraft:air",
        f"/setblock 8 170 24 {block}[facing={facing}{half}]",
        f"/tp {actor} 8.5 172 26.1 180 55",
    ))
    control.command(f"/item replace entity {actor} hotbar.0 with {block} 2")
    if is_step:
        existing = {"step-opposite-facing": "north", "step-perpendicular-facing": "west"}.get(case, facing)
        support(control, "east", f"{STEP}[facing={existing}{half}]")
    if case in ("panel-blocked", "panel-fallback-west"):
        sides = ("east", "north", "south", "west") if case == "panel-blocked" else ("east", "north", "south")
        for side in sides:
            support(control, side, "minecraft:stone")
    if case.endswith("water"):
        level = 1 if "flowing" in case else 0
        support(control, "east", f"minecraft:water[level={level}]", 2 if is_step else 1)
    if wall:
        aim = (8.5, 170.9, 24.999)
    elif is_step:
        aim = (8.9, 170.999 if upper else 170.499, 24.75)
    else:
        aim = (8.9, 170.187, 24.5)
    return block, aim


def aim_at_copycat(control, block, aim):
    control.call("wait", 3)
    control.call("select", block)
    control.call("look-at", *aim)
    control.call("wait", 4)
    target = control.call("status")["target"]
    assert target and target["pos"] == list(POS) and target["block"] == block, target


def actual_neighbors(control, block):
    found = {}
    for side, vector in DIRECTIONS.items():
        for distance in range(1, 4):
            at = tuple(origin + delta * distance for origin, delta in zip(POS, vector))
            state = control.call("block", *at)["state"]
            label, bracket, suffix = state.partition("[")
            if block == label:
                props = dict(entry.split("=", 1) for entry in suffix[:-1].split(",")) if bracket else {}
                found[f"{side}{distance}"] = (label, props)
    return found


def reference():
    with (ROOT / "fixtures/copycat-assist-java.csv").open() as trace:
        return list(csv.DictReader(trace))


def expected_neighbors(row):
    entries = (value.split("=", 1) for value in row["neighbors"].split("|") if value)
    return {side: COPYCAT.state_from_java(state) for side, state in entries}


def run(args):
    rows = reference()
    with fixture_world(args, "CopycatAssist", render=True, pack=args.pack) as control:
        control.commands((
            "/gamemode survival",
            "/fill 7 171 26 10 171 28 minecraft:smooth_stone",
        ))
        mismatches = []
        for row in rows:
            case = row["case"]
            block, aim = setup(control, case)
            aim_at_copycat(control, block, aim)
            tick = control.clock()
            control.call("mouse", "right", "click")
            control.call("wait", 4)
            assert control.clock() == tick, case
            expected = expected_neighbors(row)
            observed = actual_neighbors(control, block)
            held = control.call("inventory")["counts"].get(block, 0)
            print(case, observed, held, flush=True)
            if (observed, held) != (expected, int(row["held"])):
                mismatches.append((case, observed, held, expected, row["held"]))
        assert not mismatches, mismatches
    print(f"All {len(rows)} Java Copycat placements matched on the action tick.")

def run_lan(args, scratch):
    multiplayer = import_module("test-multiplayer")
    name = "CopycatGuest"
    samples = {"panel-blocked", "panel-up-on-wall", "step-water"}
    with fixture_world(args, "CopycatAssist-LAN", render=True, pack=args.pack) as host:
        host.command("/fill 7 171 26 10 171 28 minecraft:smooth_stone")
        network = host.call("lan", "open", "0", "commands", "force")
        with multiplayer.joined_client(args, scratch, f"127.0.0.1:{network['port']}", name,
                                       render=True, scenario="copycat-assist-lan", pack=args.pack) as guest:
            multiplayer.until("guest entered", lambda: any(
                player["name"] == name and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.command(f"/gamemode survival {name}")
            for row in reference():
                case = row["case"]
                if case not in samples:
                    continue
                block, aim = setup(host, case, name)
                multiplayer.until("guest inventory and pose", lambda: (
                    multiplayer.count(guest, block) == 2
                    and guest.call("state")["player"]["position"] == [8.5, 172.0, 26.1]
                ))
                aim_at_copycat(guest, block, aim)
                tick = host.clock()
                guest.call("mouse", "right", "click")
                guest.call("wait", 4)
                expected = expected_neighbors(row)
                multiplayer.until(case, lambda: (
                    actual_neighbors(host, block) == expected
                    and actual_neighbors(guest, block) == expected
                    and multiplayer.count(guest, block) == int(row["held"])
                ))
                assert host.clock() == tick, case
                print(case, "matched both clients", flush=True)
    print("Both clients matched all three Java Copycat placement samples on the action tick.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-ca-lan-") as scratch:
            run_lan(args, Path(scratch))
    else:
        run(args)
