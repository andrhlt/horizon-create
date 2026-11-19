#!/usr/bin/env python3
"""Check natural Sequenced Gearshift placement and real Wrench rotation against Java."""
import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world
SEQ = "create:sequenced_gearshift"
FACES = {
    "down": (0, -1, 0), "up": (0, 1, 0), "north": (0, 0, -1), "south": (0, 0, 1),
    "west": (-1, 0, 0), "east": (1, 0, 0),
}

def coords(pos):
    return " ".join(map(str, pos))

def look(control, point, support, face):
    control.call("look-at", *point)
    control.call("wait", 1)
    hit = control.call("looking-at").get("block")
    if not hit or hit["pos"] != list(support) or hit["face"] != face:
        raise RuntimeError(f"Expected the visible {face} of {support} from {point}, got {hit}.")

def click_sneaking(control, point, support, face):
    control.call("key", "shift", "down")
    control.call("wait", 4)
    try:
        look(control, point, support, face)
        control.call("mouse", "right", "click")
        control.call("wait", 3)
    finally:
        control.call("key", "shift", "up")


def mounted(axis, vertical):
    return f"{SEQ}[axis={axis},state=0,vertical={vertical}]"

def place(control, rows):
    for index, _yaw, _pitch, sneak, _direction, axis, vertical in rows:
        index = int(index)
        commands = ["/fill 4 101 -15 13 107 -5 minecraft:air"]
        if index in (0, 4, 5):
            pos = (8,102,-10)
            support, face, point = (8,102,-9), "north", (8.5,102.5,-9.001)
            feet = (8.5,101.0,-12.5)
        elif index == 1:
            pos = (8,102,-10)
            support, face, point = (7,102,-10), "east", (7.999,102.5,-9.5)
            feet = (11.5,101.0,-9.5)
        elif index == 6:
            pos = (8,102,-10)
            support, face, point = (9,102,-10), "west", (9.001,102.5,-9.5)
            feet = (5.5,101.0,-9.5)
            commands.append("/setblock 8 101 -10 create:shaft[axis=y]")
        elif index in (2, 7):
            pos = (8,101,-10)
            support, face, point = (8,100,-10), "up", (8.5,100.999,-9.5)
            feet = (8.5,103.0,-10.06)
            commands.append("/setblock 8 102 -11 minecraft:stone")
        else:
            pos = (8,104,-10)
            support, face, point = (8,105,-10), "down", (8.5,105.001,-9.5)
            feet = (8.9,101.0,-9.5)
        commands.extend((
            f"/setblock {coords(support)} minecraft:stone",
            f"/tp @s {coords(feet)}",
            f"/item replace entity @s hotbar.0 with {SEQ}",
        ))
        if index in (4, 5, 7):
            x, y, z = pos
            commands.append(f"/setblock {x + 1} {y} {z} create:shaft[axis=x]")
        if index == 7:
            x, y, z = pos
            commands.append(f"/setblock {x} {y} {z + 1} create:shaft[axis=z]")
        control.commands(commands)
        control.call("wait", 3)
        control.call("select", SEQ)
        if sneak == "true":
            control.call("key", "shift", "down")
            control.call("wait", 2)
        try:
            look(control, point, support, face)
            control.call("script", script="mouse right down\nmouse right up\nwait 4\n")
        finally:
            if sneak == "true":
                control.call("key", "shift", "up")
        actual = control.call("block", *pos)["state"]
        if actual != mounted(axis, vertical):
            raise RuntimeError(f"Placement {index} gave {actual}, expected {mounted(axis, vertical)}.")
        if control.call("state")["screen"] == "mod":
            control.call("close")
            control.call("wait", 1)
    print(f"Natural by-hand Sequenced Gearshift placement matched all {len(rows)} Java rows.")

def wrench(control, rows):
    pos = (8,104,-10)
    control.commands((
        "/fill 4 101 -15 13 107 -5 minecraft:air",
        "/setblock 10 104 -10 minecraft:stone",
        "/item replace entity @s hotbar.0 with create:wrench",
    ))
    control.call("wait", 3)
    control.call("select", "create:wrench")
    for before, was_vertical, face, after, vertical, success in rows:
        direction = FACES[face]
        control.call("command", f"/setblock {coords(pos)} {mounted(before, was_vertical)}")
        camera = (10.5, 105.0, -9.5) if face == "up" else (
            8.5 + direction[0] * 3.0, 101.0, -9.5 + direction[2] * 3.0,
        )
        control.call("command", f"/tp @s {coords(camera)}")
        control.call("wait", 3)
        player = control.call("state")["player"]
        used = control.call("interact", *pos, face)
        control.call("wait", 2)
        actual = control.call("block", *pos)["state"]
        screen = control.call("state")["screen"]
        if success != "true" or screen != "playing" or actual != mounted(after, vertical):
            raise RuntimeError(f"Wrench {before} vertical={was_vertical} from {face}: {actual}, expected {mounted(after, vertical)}; {used}, screen={screen}, player={player}.")
    print(f"Ordinary Wrench clicks matched all {len(rows)} Java axis and posture cases.")

def pickup(control):
    control.command(f"/setblock 8 104 -10 {mounted('z', 'true')}")
    control.command("/tp @s 10.500 105.000 -9.500")
    control.call("wait", 3)
    click_sneaking(control, (8.5, 104.999, -9.5), (8, 104, -10), "up")
    used = control.call("state")
    if used["screen"] != "playing" or (
        control.call("block", 8, 104, -10)["block"] != "minecraft:air"
        or control.call("inventory")["counts"].get(SEQ, 0) != 1
    ):
        raise RuntimeError(f"Survival wrench pickup should return one Sequenced Gearshift, got {used}.")
    print("Sneak-wrench pickup removed the gearshift and returned one item, as in Java.")


def multiplayer_wrench(args, scratch):
    spec = spec_from_file_location("multiplayer_fixture", ROOT / "tools/test-multiplayer.py")
    multiplayer = module_from_spec(spec)
    spec.loader.exec_module(multiplayer)
    guest_name = "SeqWrench"
    pos = (8, 104, -10)
    with fixture_world(args, "SequencerOrientationLAN", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 4 100 -14 14 100 -5 minecraft:smooth_stone",
            "/fill 4 101 -13 14 106 -6 minecraft:air",
            f"/setblock 8 104 -10 {mounted('x', 'false')}",
            "/tp @s 12.500 101.000 -8.500",
        ))
        host.step_to(host.clock() + 1)
        address = f"127.0.0.1:{host.call('lan', 'open', '0', 'commands', 'force')['port']}"
        with multiplayer.joined_client(
            args, scratch, address, guest_name, render=True, scenario="sequencer-wrench-lan", pack=args.pack,
        ) as guest:
            multiplayer.until("the wrench guest to join", lambda: any(
                user["name"] == guest_name and user["placed"] for user in host.call("lan", "status")["guests"]
            ))
            host.commands((
                f"/gamemode survival {guest_name}",
                f"/tp {guest_name} 8.500 101.000 -6.500",
                f"/item replace entity {guest_name} hotbar.0 with create:wrench",
            ))
            multiplayer.until("the guest to reach the gearshift", lambda: (
                guest.call("state")["player"]["position"] == [8.5, 101.0, -6.5]
                and guest.call("inventory")["counts"].get("create:wrench") == 1
                and guest.call("block", *pos)["state"] == mounted("x", "false")
            ))
            guest.call("select", "create:wrench")
            guest.call("interact", *pos, "south")
            multiplayer.until("both players to see the upright gearshift", lambda: all(
                peer.call("block", *pos)["state"] == mounted("x", "true") for peer in (host, guest)
            ))
            if guest.call("state")["screen"] != "playing":
                raise RuntimeError("Turning the gearshift with a Wrench opened the editor.")
            click_sneaking(guest, (8.5, 104.50, -9.001), pos, "south")
            multiplayer.until("both players to see the retrieved gearshift", lambda: all(
                peer.call("block", *pos)["block"] == "minecraft:air" for peer in (host, guest)
            ))
            multiplayer.until("the guest to receive one gearshift", lambda: (
                guest.call("inventory")["counts"].get(SEQ) == 1
            ))

def java_rows(name):
    with (ROOT / "fixtures" / f"sequenced-gearshift-{name}-java.csv").open(newline="") as reference:
        reader = csv.reader(reference)
        next(reader)
        return list(reader)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-orl-") as tmp:
            multiplayer_wrench(args, Path(tmp))
        print("A survival guest wrenched and picked up the upright gearshift. Both clients saw the same state.")
        return

    placement = java_rows("orientation")
    rotation = java_rows("wrench")
    if len(placement) != 8 or len(rotation) != 24:
        raise RuntimeError(f"Missing Java placement or wrench rows. Found {len(placement)} and {len(rotation)}.")
    with fixture_world(args, "SequencerOrientation", render=True, pack=args.pack) as control:
        control.commands((
            "/fill 4 100 -15 14 100 -5 minecraft:smooth_stone",
            "/gamemode survival",
        ))
        place(control, placement)
        wrench(control, rotation)
        pickup(control)


if __name__ == "__main__":
    main()
