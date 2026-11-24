#!/usr/bin/env python3
"""Exercise two independent straight train carriages through reopen and restore."""
import argparse
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import fixture_world

train = import_module("test-simple-train")
mp = import_module("test-multiplayer")
X, Y, Z = train.X, train.Y, train.Z
BOGEYS = (X + 1, X + 4, X + 8, X + 11)
STOPS = ((X + 1, X + 4), (X + 8, X + 11))


def click_track(control, x):
    control.call("look-at", x + .5, Y + .06, Z + .5)
    control.call("mouse", "right", "click")
    control.call("wait", 3)


def assemble_setup(control):
    control.commands((
        f"/fill {X-21} {Y-1} {Z-5} {X+25} {Y-1} {Z+5} minecraft:smooth_stone",
        f"/fill {X-20} {Y} {Z} {X+24} {Y} {Z} create:track[shape=xo]",
        "/gamemode survival",
        f"/tp @s {X+2.5} {Y} {Z+.5} 90 20",
        "/item replace entity @s hotbar.0 with create:track_station",
    ))
    control.call("wait", 3)
    control.call("key", "1", "tap")
    click_track(control, X)
    sx, sy, sz = train.STATION
    control.command(f"/tp @s {sx+.5} {sy} {sz+2.5} 180 20")
    control.call("wait", 3)
    control.call("interact", sx, sy-1, sz, "up")
    control.step_to(control.clock()+1)
    control.call("wait", 3)
    control.call("interact", *train.STATION, "up")
    control.call("wait", 4)
    control.call("click-button", "Create New Train")
    control.step_to(control.clock()+1)
    control.call("wait", 2)
    control.call("key", "esc", "tap")
    control.command("/item replace entity @s hotbar.0 with create:railway_casing 4")
    control.call("wait", 2)
    for x in BOGEYS:
        control.command(f"/tp @s {x+.5} {Y} {Z-1.6} 0 20")
        control.call("wait", 2)
        click_track(control, x)
        if control.call("block", x, Y+1, Z)["block"] != "create:small_bogey":
            raise RuntimeError(f"Bogey placement failed at {x}")
    for left, right in STOPS:
        control.command(f"/fill {left} {Y+2} {Z} {right} {Y+2} {Z} minecraft:oak_planks")
        control.command(f"/setblock {left} {Y+3} {Z} create:controls[facing=east]")
        control.command(f"/setblock {left+1} {Y+2} {Z} minecraft:barrel")
        control.command(f"/item replace block {left+1} {Y+2} {Z} container.0 with minecraft:iron_ingot 7")
    control.command("/item replace entity @s hotbar.0 with create:super_glue")
    control.call("wait", 2)
    # Glue each car independently: bogey, its body, forward controls.
    for left, right in STOPS:
        for x, yy in ((right, Y+1), (left, Y+3)):
            control.command(f"/tp @s {x+.5} {min(Y+1.5, yy-1.)} {Z-1.7} 0 0")
            control.call("wait", 2)
            control.call("look-at", x+.5, yy+.45, Z+.5)
            control.call("mouse", "right", "click")
            control.call("wait", 2)
    sx, sy, sz = train.STATION
    control.command(f"/item replace entity @s hotbar.0 with minecraft:air")
    control.command(f"/tp @s {sx+.5} {sy} {sz+2.5} 180 20")
    control.call("wait", 3)
    # The fixture freezes game time; let the station refresh its cached bogey count.
    control.step_to(control.clock()+1)
    control.call("interact", *train.STATION, "up")
    control.call("wait", 4)
    control.call("click-button", "Assemble Train")
    control.step_to(control.clock()+1)
    control.call("wait", 3)
    if "assembling=false" not in control.call("block", *train.STATION)["state"]:
        raise RuntimeError("Two-carriage straight assembly was rejected")
    control.call("key", "esc", "tap")
    control.call("wait", 2)


def assert_assembled(client, *, verify_payload=True):
    for x in BOGEYS:
        if client.call("block", x, Y+1, Z)["block"] != "minecraft:air":
            raise RuntimeError(f"Assembled bogey block remained at {x}")
    if verify_payload:
        payload = client.command(
            "/data get entity @e[type=minecraft:interaction,nbt={CreateTrain:{}},limit=1,sort=nearest] CreateTrain"
        )
        if "BogeyOffsets: [I; 0, 3, 7, 10]" not in payload:
            raise RuntimeError(f"Assembled train bogey offsets were missing: {payload}")
        for block, count in (("create:small_bogey", 4), ("create:controls", 2), ("minecraft:barrel", 2)):
            found = payload.count(f'Name: "{block}"')
            if found != count:
                raise RuntimeError(f"Assembled component capture had {found} {block} blocks, expected {count}")


def assert_restored(client):
    for x in BOGEYS:
        if client.call("block", x, Y+1, Z)["block"] != "create:small_bogey":
            raise RuntimeError(f"Disassembly did not restore bogey at {x}")
    for left, right in STOPS:
        for x in range(left, right+1):
            if client.call("block", x, Y+2, Z)["block"] not in ("minecraft:oak_planks", "minecraft:barrel"):
                raise RuntimeError(f"Disassembly did not restore carriage block at {x}")
        inventory = client.command(f"/data get block {left+1} {Y+2} {Z} Items")
        if "minecraft:iron_ingot" not in inventory or "count: 7" not in inventory:
            raise RuntimeError(f"Disassembly lost carriage cargo: {inventory}")


def drive_and_assert(host):
    controls_x = STOPS[1][0]
    host.command("/attribute @s minecraft:movement_speed base set 0")
    host.command(f"/tp @s {controls_x+.5} {Y} {Z-1.3} 0 20")
    host.call("wait", 3)
    host.call("look-at", controls_x+.5, Y+3.45, Z+.5)
    host.call("mouse", "right", "click")
    host.call("wait", 3)
    entity = "/data get entity @e[type=minecraft:interaction,nbt={CreateTrain:{}},limit=1,sort=nearest] CreateTrain"
    before = host.command(entity)
    host.call("key", "w", "down")
    for _ in range(40):
        host.step_to(host.clock()+1)
    host.call("key", "w", "up")
    after = host.command(entity)
    def distance(value):
        import re
        match = re.search(r"(?:Distance: )?(-?[0-9.]+)d", value)
        if not match:
            raise RuntimeError(f"Train distance was not readable: {value}")
        return float(match.group(1))
    if distance(after) <= distance(before):
        raise RuntimeError(f"The four-bogey train did not move: before={before}; after={after}")
    def points(value):
        import re
        section = re.search(r"TrackPoints: (\[.*?\]), WheelPoints:", value)
        if not section:
            raise RuntimeError(f"Train track points were not readable: {value}")
        return re.findall(r"Track: \[I; (-?\d+), (-?\d+), (-?\d+)\], Offset: (-?[0-9.]+)d", section[1])
    before_points, after_points = points(before), points(after)
    if len(after_points) != 8 or len(before_points) != 8:
        raise RuntimeError(f"Expected eight bogey track points, got {len(before_points)} then {len(after_points)}")
    if any(old == new for old, new in zip(before_points, after_points, strict=True)):
        raise RuntimeError(f"At least one bogey pair failed to follow the moving train: {before_points} -> {after_points}")


def run(args):
    with TemporaryDirectory(prefix="hc-train-multi-", dir="/private/tmp") as scratch:
        with fixture_world(args, "TrainMultiCarriage", train.STRUCTURE, render=True,
                           pack=args.pack, env={"HORIZON_NO_AUDIO": "1"}) as host:
            assemble_setup(host)
            assert_assembled(host)
            host.restart()
            assert_assembled(host)
            port = host.call("lan", "open", "0", "commands", "force")["port"]
            with mp.joined_client(args, Path(scratch), f"127.0.0.1:{port}", "TrainGuest",
                                  scenario="train-multi-carriage", pack=args.pack,
                                  env={"HORIZON_NO_AUDIO": "1"}) as guest:
                mp.until("guest joins", lambda: any(p["name"] == "TrainGuest" and p["placed"]
                                                     for p in host.call("lan", "status")["guests"]))
                assert_assembled(guest, verify_payload=False)
                sx, sy, sz = train.STATION
                host.command(f"/tp @s {sx+.5} {sy} {sz+2.5} 180 20")
                host.call("wait", 3)
                host.call("interact", *train.STATION, "up")
                host.call("wait", 4)
                host.call("click-button", "Disassemble Train")
                host.step_to(host.clock()+1)
                host.call("wait", 3)
                host.call("key", "esc", "tap")
                assert_restored(host)
                mp.until("guest sees restored carriages", lambda: all(
                    guest.call("block", x, Y+1, Z)["block"] == "create:small_bogey" for x in BOGEYS))
                for x in BOGEYS:
                    if guest.call("block", x, Y+1, Z)["block"] != "create:small_bogey":
                        raise RuntimeError(f"Guest did not converge on restored bogey at {x}")
                for left, right in STOPS:
                    for x in range(left, right+1):
                        if guest.call("block", x, Y+2, Z)["block"] not in ("minecraft:oak_planks", "minecraft:barrel"):
                            raise RuntimeError(f"Guest did not converge on restored carriage block at {x}")
        with fixture_world(args, "TrainMultiCarriageMotion", train.STRUCTURE, render=True,
                           pack=args.pack, env={"HORIZON_NO_AUDIO": "1"}) as motion:
            assemble_setup(motion)
            assert_assembled(motion)
            drive_and_assert(motion)
    print("Two glued straight carriages assembled, moved, survived reopen, converged on LAN, and restored their blocks and cargo.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    run(parser.parse_args())
