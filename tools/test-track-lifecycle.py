#!/usr/bin/env python3
"""Mine a saved curved track endpoint and check the reciprocal link and track drops."""

import argparse
import csv
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

track_curve = import_module("test-track-curve")

TRACK = "create:track"
PICK = "minecraft:netherite_pickaxe"
FLOOR = "/fill -11 111 -24 25 111 7 minecraft:smooth_stone"
GUEST = "TrackGuest"


def ends(case):
    return tuple(
        track_curve.add(track_curve.START, tuple(int(case[f"p{index}_{axis}"]) for axis in "xyz"))
        for index in (1, 2)
    )


def counterpart(control, endpoint):
    stored = control.command(
        f"/data get block {track_curve.coordinates(endpoint)} Connections[0].Positions[1].Pos"
    )
    return track_curve.add(endpoint, track_curve.vector(stored))


def mine(control, endpoint):
    x, y, z = endpoint
    control.commands((
        f"/tp @s {x + 0.5} {y} {z - 1.5}",
        f"/item replace entity @s hotbar.0 with {PICK}",
    ))
    control.call("wait", 3)
    control.call("select", PICK)
    control.call("look-at", x + 0.5, y + 0.06, z + 0.5)
    control.call("mouse", "left", "down")
    try:
        for _ in range(90):
            at = track_curve.coordinates(endpoint)
            if control.command(f"/execute if block {at} minecraft:air") == "Test passed":
                return
            control.step_to(control.clock() + 1)
    finally:
        control.call("mouse", "left", "up")
    raise RuntimeError(f"Could not mine track at {endpoint}")


def collect(control, item):
    drops = f'@e[type=minecraft:item,nbt={{Item:{{id:"{item}"}}}}]'
    control.command(f"/tp {drops} @s")
    control.command("/tick step 25")
    control.call("wait", 27)
    return control.call("inventory")["counts"].get(item, 0)


def check_disconnected(control, endpoint):
    at = track_curve.coordinates(endpoint)
    state = control.command(f"/execute if block {at} create:track[turn=false]")
    tag = control.command(f"/data get block {at} Connections")
    assert state == "Test passed" and tag.endswith("[]"), (endpoint, state, tag)


def check_removal(control, removed, remaining, expected_drops):
    check_disconnected(control, remaining)
    found = collect(control, TRACK)
    if found != expected_drops:
        raise RuntimeError(f"Removing {removed} recovered {found}/{expected_drops} tracks")


def casing(control):
    pos = (5, 112, -8)
    control.commands((
        "/setblock 5 112 -8 create:brass_casing",
        "/tp @s 3.5 112 -7.5",
        "/item replace entity @s hotbar.0 with create:sturdy_sheet 2",
    ))
    control.call("wait", 3)
    control.call("select", "create:sturdy_sheet")
    control.call("interact", *pos, "up")
    control.call("wait", 3)
    assert control.call("block", *pos)["block"] == "create:railway_casing"
    assert control.call("inventory")["counts"].get("create:sturdy_sheet") == 1
    mine(control, pos)
    assert collect(control, "create:railway_casing") == 1
    print("The survival player applied a Sturdy Sheet to Brass Casing and recovered one Railway Casing.", flush=True)


def straight_and_slope(control):
    for x, shape in ((8, "xo"), (13, "ae")):
        pos = (x, 112, -11)
        floor = (x, 111, -11)
        control.call("command", "/clear @s create:track")
        control.commands((
            f"/tp @s {x + 0.5} 112 -12.5 -90 20",
            "/item replace entity @s hotbar.0 with create:track",
        ))
        if shape == "ae":
            control.command(f"/setblock {x + 1} 112 -11 minecraft:stone")
        control.call("wait", 3)
        control.call("select", TRACK)
        control.call("interact", *floor, "up")
        placed = control.command(
            f"/execute if block {track_curve.coordinates(pos)} create:track[shape={shape}]"
        )
        assert placed == "Test passed", (shape, placed)
        control.commands((
            "/attribute @s minecraft:gravity base set 0.08",
            f"/tp @s {x + 0.5} 114 -10.5",
            "/tick step 24",
        ))
        control.call("wait", 26)
        landed = track_curve.vector(control.command("/data get entity @s Pos"))
        expected_y = 112.125 if shape == "xo" else 112.0
        assert abs(landed[1] - expected_y) < 1e-5, (shape, expected_y, landed)
        control.command("/attribute @s minecraft:gravity base set 0")
        mine(control, pos)
        assert collect(control, TRACK) == 1, shape
    control.call("command", "/clear @s create:track")
    print("Survival construction and pickaxe removal recovered the straight and ascending track pieces.", flush=True)


def solo(args, curves):
    with (ROOT / "fixtures/track_removal-java.csv").open() as file:
        removal = list(csv.DictReader(file))
    with fixture_world(args, "Track-lifecycle", render=True, pack=args.pack) as control:
        control.commands((FLOOR, "/gamemode survival", "/attribute @s minecraft:gravity base set 0"))
        casing(control)
        straight_and_slope(control)
        for index, row in enumerate(removal):
            case = curves[row["case"]]
            primary, secondary = ends(case)
            track_curve.test_case(control, case)
            if index == 0:
                control.command("/save-all flush")
                control.restart()
                assert counterpart(control, primary) == secondary
                assert counterpart(control, secondary) == primary
                print("The two curve endpoints retained their reciprocal links across save/reopen.", flush=True)
            changed = control.command(f"/gamerule minecraft:block_drops {row['block_drops']}")
            assert changed.endswith(f" {row['block_drops']}"), changed
            mode = "creative" if row["creative"] == "true" else "survival"
            control.call("command", f"/gamemode {mode}")
            assert row["other_has_entity"] == "false", row
            removed, remaining = (primary, secondary) if row["endpoint"] == "primary" else (secondary, primary)
            mine(control, removed)
            check_removal(control, removed, remaining, int(row["recovered"]))
            if index == 0:
                control.command("/save-all flush")
                control.restart()
                check_disconnected(control, remaining)
            control.call("command", "/clear @s create:track")
        control.command("/gamemode survival")
        case = curves["0"]
        primary, secondary = ends(case)
        track_curve.test_case(control, case)
        control.commands((
            "/clear @s create:track",
            f"/setblock {track_curve.coordinates(primary)} minecraft:air",
        ))
        check_removal(control, primary, secondary, int(removal[0]["curve_cost"]))
    print(f"All {len(removal)} Java curve removal cases matched; command replacement returned the curve cost once.")


def lan(args, case):
    multiplayer = import_module("test-multiplayer")
    primary, secondary = ends(case)
    x, y, z = track_curve.START
    start = f"{x + 0.5 - 2} {y} {z + 0.5}"
    dx, dy, dz = (int(case[axis]) for axis in ("dx", "dy", "dz"))
    target_x, target_y, target_z = track_curve.add(track_curve.START, (dx, dy, dz))
    with fixture_world(args, "Track-lan", pack=args.pack) as host:
        host.commands((
            FLOOR,
            "/tp @s 10.5 112 -13.5",
            f"/setblock {x} {y} {z} create:track[shape=xo]",
        ))
        network = host.call("lan", "open", "0", "commands", "force")
        address = f"127.0.0.1:{network['port']}"
        host.command("/tick unfreeze")
        with TemporaryDirectory(prefix="hc-track-lan-") as scratch, multiplayer.joined_client(
            args, Path(scratch), address, GUEST, render=True, scenario="track-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the guest to enter the world", lambda: any(
                player["name"] == GUEST and player["placed"]
                for player in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {GUEST}",
                f"/tp {GUEST} {start} -90 20",
                f"/item replace entity {GUEST} hotbar.0 with create:track {int(case['supplied']) + 1}",
            ))
            multiplayer.until("the guest's track stack", lambda: (
                multiplayer.count(guest, TRACK) == int(case["supplied"]) + 1
                and guest.call("state")["player"]["position"] == [float(v) for v in start.split()]
            ))
            multiplayer.until("the guest to see the starting track", lambda: (
                guest.call("block", x, y, z)["block"] == TRACK
            ))
            guest.call("select", TRACK)
            guest.call("wait", 10)
            support = [3, 111, -10]
            guest.call("look-at", 3.5, 111.95, -9.5)
            multiplayer.until("the guest to aim at the ordinary track support", lambda: (
                (guest.call("looking-at").get("block") or {}).get("pos") == support
            ))
            guest.call("mouse", "right", "click")
            try:
                multiplayer.until("the guest to place an ordinary track", lambda: (
                    host.call("block", 3, 112, -10)["block"] == TRACK
                    and multiplayer.count(guest, TRACK) == int(case["supplied"])
                ))
            except RuntimeError as error:
                host_track = host.command("/execute if block 3 112 -10 create:track")
                host_inventory = host.command(f"/data get entity {GUEST} Inventory")
                guest_track = guest.call("block", 3, 112, -10)["block"]
                guest_inventory = multiplayer.count(guest, TRACK)
                raise RuntimeError(f"{error}. Host {host_track}, {host_inventory}. "
                                   f"Guest {guest_track}, {guest_inventory}") from error
            guest.call("wait", 5)
            guest.call("look-at", x + 0.5, y + 0.06, z + 0.5)
            multiplayer.until("the guest to aim at the thin starting track", lambda: (
                (guest.call("looking-at").get("block") or {}).get("pos") == [x, y, z]
            ))
            guest.call("mouse", "right", "click")
            multiplayer.until("the host to record the guest's starting endpoint", lambda: (
                "create:track_connecting_from" in host.command(f"/data get entity {GUEST} Inventory")
            ))
            approach = [target_x + 0.5, target_y, target_z - 1.5]
            host.command(f"/tp {GUEST} {track_curve.coordinates(approach)} 0 20")
            multiplayer.until("the guest to reach the other track endpoint", lambda: (
                guest.call("state")["player"]["position"] == approach
            ))
            guest.call("interact", target_x, target_y - 1, target_z, "up")
            multiplayer.until("both curved endpoints to replicate to the guest", lambda: all(
                "turn=true" in guest.call("block", *pos)["state"] for pos in (primary, secondary)
            ))
            multiplayer.until("the guest's survival track cost to replicate", lambda: (
                multiplayer.count(guest, TRACK) == int(case["remaining"])
            ))
            assert counterpart(host, primary) == secondary
            assert counterpart(host, secondary) == primary
    print("The survival LAN guest placed the Java fixture curve, and both clients agreed on its endpoints.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--pack", type=lambda value: Path(value).resolve(strict=True))
    args = parser.parse_args()
    with (ROOT / "fixtures/track_curve-java.csv").open() as file:
        curves = {row["case"]: row for row in csv.DictReader(file)}
    if args.lan:
        lan(args, curves["0"])
    else:
        solo(args, curves)


if __name__ == "__main__":
    main()
