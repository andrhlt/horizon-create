#!/usr/bin/env python3
"""Replay Create Desk Bell presses, retrigger, redstone output and local audio."""

import argparse
import csv
from importlib import import_module
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

crafting = import_module("test-machine-crafting")
multiplayer = import_module("test-multiplayer")
BELL = "create:desk_bell"
GUEST = "DeskBellGuest"
AT = (9, 171, 20)
DIRECT_WIRE = (9, 170, 19)
WEAK_WIRE = (10, 171, 20)
FACE_OFFSETS = {
    "down": (0, -1, 0), "up": (0, 1, 0),
    "north": (0, 0, -1), "south": (0, 0, 1),
    "west": (-1, 0, 0), "east": (1, 0, 0),
}


def state(actor, pos):
    block = actor.call("block", *pos)
    return dict(re.findall(r"(\w+)=(\w+)", block["state"]))


def sound_cues(actor):
    log = actor.socket.parent / "ctl.log"
    marker = "CREATE_ELEVATOR_PLAYBACK "
    if not log.is_file():
        return []
    cues = []
    for line in log.read_text().splitlines():
        if marker not in line:
            continue
        sound, category, x, y, z, volume, pitch = line.split(marker, 1)[1].split(",")
        if sound == BELL:
            cues.append((int(category), tuple(map(float, (x, y, z))), float(volume), float(pitch)))
    return cues


def exercise(host, actor, player, expected, sounds):
    press_ticks = {int(sound["tick"]) for sound in sounds}
    host.commands((
        f"/clear {player}",
        f"/tp {player} 9.5 171 22.5",
    ))
    multiplayer.until("the player to reach the bell", lambda:
                      actor.call("state")["player"]["position"] == [9.5, 171, 22.5])
    actor.call("look-at", 9.5, 171.35, 20.5)
    multiplayer.until("the desk bell to be targeted", lambda:
                      (actor.call("looking-at").get("block") or {}).get("pos") == list(AT))
    start = host.clock()
    errors = []
    for row in expected:
        tick = int(row["tick"])
        if tick:
            host.step_to(start + tick)
        if tick in press_ticks:
            actor.call("mouse", "right", "click")
            actor.call("wait", 4)
        elif tick == 44:
            host.command("/setblock 9 171 20 minecraft:air")
        wanted = row["powered"], row["wire"], row["strong"]
        got = state(host, AT).get("powered", "false"), state(host, WEAK_WIRE).get("power"), state(host, DIRECT_WIRE).get("power")
        if got != wanted:
            errors.append((tick, got, wanted))
        if actor is not host:
            multiplayer.until(f"both redstone circuits at Java tick {tick} to synchronize", lambda: (
                state(actor, AT).get("powered", "false"),
                state(actor, WEAK_WIRE).get("power"),
                state(actor, DIRECT_WIRE).get("power"),
            ) == got)
    if errors:
        raise RuntimeError(f"Desk Bell differed on {len(errors)} ticks. First {errors[:5]}.")
    expected_cues = [(
        int(sound["category"]),
        tuple(cell + float(sound[axis]) for cell, axis in zip(AT, ("x", "y", "z"), strict=True)),
        float(sound["volume"]),
        float(sound["pitch"]),
    ) for sound in sounds if sound["sound"] == BELL]
    for client in (host,) if actor is host else (host, actor):
        multiplayer.until("the original dings to play", lambda: len(sound_cues(client)) >= len(expected_cues))
        actual_cues = sound_cues(client)
        if actual_cues != expected_cues:
            raise RuntimeError(f"Desk Bell audio was {actual_cues}, Java played {expected_cues}.")


def placement(host, actor, player, wet):
    reference = "desk-bell-water-java.csv" if wet else "desk-bell-placement-java.csv"
    with (ROOT / "fixtures" / reference).open() as source:
        rows = list(csv.DictReader(source))
    for index, row in enumerate(rows):
        face = row["face"]
        offset = FACE_OFFSETS[face]
        support = (7 + 5 * index, {"down": 175, "up": 170}.get(face, 172), 20)
        target = tuple(cell + step for cell, step in zip(support, offset, strict=True))
        feet = (support[0] + .5 + 2 * offset[0], 171, 20.5 + 2 * offset[2])
        if face in ("down", "up"):
            feet = (feet[0], feet[1], feet[2] + 2)
        aim = tuple(cell + .5 + .5 * step for cell, step in zip(support, offset, strict=True))
        if wet:
            host.command(f"/setblock {' '.join(map(str, target))} minecraft:water")
        host.commands((
            f"/setblock {' '.join(map(str, support))} minecraft:stone",
            f"/tp {player} {' '.join(map(str, feet))}",
            f"/item replace entity {player} hotbar.0 with {BELL}",
        ))
        multiplayer.until("the player to receive one bell and arrive", lambda: (
            actor.call("inventory")["counts"].get(BELL) == 1
            and actor.call("state")["player"]["position"] == list(feet)
        ))
        actor.call("select", BELL)
        actor.call("look-at", *aim)
        def target_is_support():
            hit = actor.call("looking-at").get("block") or {}
            return hit.get("pos") == list(support) and hit.get("face") == face
        multiplayer.until(f"aim to reach the support's {face} face", target_is_support)
        actor.call("mouse", "right", "click")
        wanted = {"facing": row["facing"], "powered": "false", "waterlogged": row.get("waterlogged", "false")}
        multiplayer.until(f"the bell to settle at the Java {face} orientation", lambda: (
            host.call("block", *target)["block"] == BELL and state(host, target) == wanted
        ))
        multiplayer.until(f"the {face} bell and consumed item to synchronize", lambda: (
            state(actor, target) == wanted and BELL not in actor.call("inventory")["counts"]
        ))
        if not wet:
            actor.call("look-at", *(cell + .5 for cell in target))
            axis = next(index for index, step in enumerate(offset) if step)
            bound = ("max" if offset[axis] > 0 else "min") + "_" + "xyz"[axis]
            expected_hit = target[axis] + float(row[bound])

            def reaches_outline():
                hit = actor.call("looking-at").get("block") or {}
                return (hit.get("pos") == list(target) and hit.get("face") == face
                        and abs(hit["point"][axis] - expected_hit) < 1e-5)

            multiplayer.until(f"the ray to reach the Java {face} bell's outer plane", reaches_outline)
    condition = "waterlogged state" if wet else "dry state and outer outline plane"
    print(f"Desk Bell survival placement matched the original Java {condition} on all {len(rows)} faces.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("ctl", "client", "resources"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    placement_mode = parser.add_mutually_exclusive_group()
    placement_mode.add_argument("--placement", action="store_true")
    placement_mode.add_argument("--wet-placement", action="store_true")
    args = parser.parse_args()
    os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    with (ROOT / "fixtures" / "desk-bell-pulse-java.csv").open() as source:
        expected = list(csv.DictReader(source))
    with (ROOT / "fixtures" / "desk-bell-sound-java.csv").open() as source:
        sounds = list(csv.DictReader(source))
    with fixture_world(args, "Desk Bell pulse", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 6 170 19 14 170 27 minecraft:stone",
            "/setblock 9 169 19 minecraft:stone",
            "/setblock 9 170 19 minecraft:redstone_wire",
            f"/setblock 9 171 20 {BELL}",
            "/setblock 10 171 20 minecraft:redstone_wire",
            "/fill 10 169 23 15 169 28 minecraft:stone",
            "/setblock 12 170 24 minecraft:crafting_table",
            "/tp @s 12.5 170 26.5",
            "/gamemode survival",
        ))
        if args.placement or args.wet_placement:
            host.command("/fill 4 170 17 36 170 23 minecraft:stone")
        if args.lan:
            port = host.call("lan", "open", 0, "commands", "force")["port"]
            with TemporaryDirectory(prefix="hc-desk-bell-") as scratch, multiplayer.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", GUEST, render=True,
                scenario="desk-bell-pulse", pack=args.pack,
            ) as guest:
                multiplayer.until("the guest to join", lambda: any(
                    player["name"] == GUEST and player["placed"]
                    for player in host.call("lan", "status")["guests"]
                ))
                host.command(f"/gamemode survival {GUEST}")
                if args.placement or args.wet_placement:
                    return placement(host, guest, GUEST, args.wet_placement)
                exercise(host, guest, GUEST, expected, sounds)
        elif args.placement or args.wet_placement:
            return placement(host, host, "@s", args.wet_placement)
        else:
            crafting.replay(host, {
                "recipe": "crafting/logistics/desk_bell", "width": "2",
                "slots": "create:andesite_casing,create:golden_sheet",
                "output": BELL, "count": "1", "remainder": "",
            })
            exercise(host, host, "@s", expected, sounds)
    print(f"Desk Bell and both circuits matched {len(expected)} original Java ticks and three cues.")


if __name__ == "__main__":
    main()
