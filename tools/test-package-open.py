#!/usr/bin/env python3
"""Compare Java's original held-package crouch openings through Horizon input."""
import argparse
import csv
from importlib import import_module
from math import floor
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world


attrs = import_module("test-attribute-filter-kinds")
package = import_module("test-package-filter-editor")
filters = package.filters
editor = filters.editor
parse = package.parsing
FEET = (8.5, 101, -11.5)
SUPPLY = (9, 101, -12)
POP_CUES = ("create:package_pop", "create:package_pop_compounded_1")


def decoded(value):
    return attrs.original_string(value)


def seed_package(host, actor, name, stack):
    supply = editor.xyz(SUPPLY)
    sample = attrs.component_format(stack)
    host.commands((
        f"/clear {name}",
        f"/setblock {supply} minecraft:barrel",
        f"/data merge block {supply} {{Items:[{{Slot:0b,{sample[1:]}]}}",
    ))
    actor.call("interact", *SUPPLY, "west")
    item = parse(sample)["id"]
    editor.wait_for(actor, "the original packaged item in the supply barrel", lambda: any(
        entry["slot"] == 300 and entry.get("stack") and entry["stack"]["item"] == item
        for entry in actor.call("menu").get("slots", [])
    ))
    actor.call("click-slot", 300)
    actor.call("click-slot", 0)
    actor.call("close")
    editor.wait_for(actor, "a single original package in hand", lambda:
        actor.call("inventory")["counts"] == {item: 1}
    )
    actor.call("select", item)
    return item


def cargo(host, name):
    message = host.command(f"/data get entity {name} Inventory")
    return parse(message.split("entity data: ", 1)[1])


def stacks(items):
    fields = {}
    for item in items:
        value = item.get("components", {}).get("minecraft:custom_name")
        fields[int(item["Slot"])] = (item["id"], item["count"], value)
    return fields


def playback(control):
    prefix = "CREATE_ELEVATOR_PLAYBACK "
    log = control.socket.parent / "ctl.log"
    heard = []
    for line in log.read_text().splitlines():
        if prefix not in line:
            continue
        sound, category, x, y, z, volume, pitch = line.split(prefix, 1)[1].split(",")
        if sound in POP_CUES:
            heard.append((sound, int(category), tuple(map(float, (x, y, z))), float(volume), float(pitch)))
    return heard


def original_cues(row):
    cues = []
    for cue in row.split(";"):
        sound, category, x, y, z, volume, pitch = cue.split("|")
        position = tuple(floor(origin) + float(delta) for origin, delta in zip(FEET, (x, y, z), strict=True))
        cues.append((sound, int(category), position, float(volume), float(pitch)))
    assert tuple(sound for sound, *_ in cues) == POP_CUES, cues
    return cues


def run_open(host, actor, name, row, *, expected_cues):
    index, hand, source, java_inventory, java_drops, pigs, _ = row
    index = int(index)
    offhand = hand == "OFF_HAND"
    expected = stacks(parse(attrs.component_format(decoded(java_inventory))))
    host.call("command", "/kill @e[type=minecraft:item]")
    host.call("command", f"/gamemode {'creative' if index == 3 else 'survival'} {name}")
    host.command(f"/tp {name} {editor.xyz(FEET)} 0 -70")
    editor.wait_for(actor, "the original player's opening position", lambda:
        tuple(actor.call("state")["player"]["position"][:3]) == FEET
    )
    package_item = seed_package(host, actor, name, decoded(source))
    if offhand:
        actor.call("key", "f", "tap")
        editor.wait_for(actor, "the original package to enter the off hand", lambda:
            actor.call("inventory")["offhand"]["item"] == package_item
        )
    if index in (4, 5):
        slots = [f"hotbar.{number}" for number in range(0 if offhand else 1, 9)]
        slots += [f"inventory.{number}" for number in range(27)]
        host.commands(f"/item replace entity {name} {slot} with minecraft:stone 64" for slot in slots)
        editor.wait_for(actor, "the original full player inventory", lambda:
            actor.call("inventory")["counts"].get("minecraft:stone") == len(slots) * 64
        )

    host.command(f"/tp {name} {editor.xyz(FEET)} 0 -70")
    editor.wait_for(actor, "the original clear off-ground view", lambda:
        not actor.call("looking-at").get("block")
    )
    if index == 0:
        host.commands((
            f"/setblock {editor.xyz(SUPPLY)} minecraft:air",
            "/setblock 10 101 -12 minecraft:stone",
        ))
        actor.call("look-at", 10.01, 101.5, -11.5)
        editor.wait_for(actor, "the original Stone target", lambda:
            (actor.call("looking-at").get("block") or {}).get("pos") == [10, 101, -12]
        )

    opening_tick = host.clock()
    actor.call("key", "shift", "down")
    try:
        editor.wait_for(actor, "the player to crouch", lambda:
            actor.call("state")["player"]["sneaking"]
        )
        actor.call("wait", 6)
        actor.call("mouse", "right", "click")
        editor.wait_for(host, f"crouch opening {index} to deliver the original exact inventory", lambda:
            stacks(cargo(host, name)) == expected
        )
        editor.wait_for(actor, "the opened package to leave the client inventory", lambda:
            package_item not in actor.call("inventory")["counts"]
        )
    finally:
        actor.call("key", "shift", "up")

    assert host.clock() == opening_tick, index

    if expected_cues is not None:
        for peer in (host,) if actor is host else (host, actor):
            editor.wait_for(peer, f"crouch opening {index} to play both original cues", lambda:
                playback(peer) == expected_cues
            )

    expected_drops = parse(decoded(java_drops))
    if expected_drops:
        message = host.command("/data get entity @e[type=minecraft:item,sort=nearest,limit=1] Item")
        actual = parse(message.split("entity data: ",1)[1])
        assert actual == expected_drops[0], (index, actual, expected_drops)
    else:
        message = host.command("/execute if entity @e[type=minecraft:item]")
        assert message.startswith("Test failed"), (index, message)
    message = host.command("/execute if entity @e[type=minecraft:pig]")
    assert message.startswith("Test passed") == (pigs == "1"), (index, message)


def measured(args, temporary):
    with (ROOT / "fixtures/package-open-java.csv").open(newline="") as file:
        rows = list(csv.reader(file))
    assert len(rows) == 7
    name = "PackageOpenLAN" if args.lan else "PackageOpen"
    with fixture_world(args, name, render=True, pack=args.pack) as host:
        host.commands((
            "/fill 4 100 -14 16 100 -4 minecraft:smooth_stone",
            "/fill 4 101 -14 16 110 -4 minecraft:air",
        ))
        with filters.actor_for(host, args, temporary if args.lan else None) as (actor, name):
            cues = []
            for row in rows:
                cues.extend(original_cues(row[-1]))
                run_open(host, actor, name, row, expected_cues=cues if args.sound else None)
    role = "Guest" if args.lan else "Host"
    print(f"{role} matched seven original Java package openings, with exact inventory, spills, and a spawned pig.")
    if args.sound:
        print(f"Each connected client played all {len(cues)} original sound events at the exact positions and settings.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ("ctl", "client", "resources"):
        parser.add_argument(parameter, type=lambda value: Path(value).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--sound", action="store_true")
    args = parser.parse_args()
    if args.sound:
        os.environ["HORIZON_CREATE_ELEVATOR_TRACE"] = "1"
    with TemporaryDirectory(prefix="hc-package-open-") as scratch:
        measured(args, Path(scratch))


if __name__ == "__main__":
    main()
