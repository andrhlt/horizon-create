#!/usr/bin/env python3
"""Replay the Java Train Schedule's component-preserving item-copy recipe."""

import argparse
import json
from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

ENTRY = run_path(str(ROOT / "tools/test-train-schedule-entry.py"))
MULTIPLAYER = run_path(str(ROOT / "tools/test-multiplayer.py"))
SCHEDULE = "create:schedule"
COMPONENT = "create:train_schedule"
GUEST = "CopyGuest"
SOURCE = (
    SCHEDULE + '[minecraft:custom_name="Route Master",'
    'minecraft:enchantments={"minecraft:unbreaking":1},'
    'minecraft:stored_enchantments={"minecraft:mending":1}]'
)


def setup(control, player):
    control.commands((
        f"/item replace entity {player} hotbar.0 with {SOURCE}",
        f"/item replace entity {player} hotbar.1 with {SCHEDULE} 3",
        f"/item replace entity {player} hotbar.2 with minecraft:paper",
        f"/item replace entity {player} hotbar.3 with {SCHEDULE}",
    ))


def components(stack):
    return ENTRY["snbt"](stack.get("components") or "{}")


def hotbar(control, slot):
    return next(entry for entry in control.call("inventory")["hotbar"] if entry["slot"] == slot)


def grid(control):
    return {entry["slot"]: entry["stack"] for entry in control.call("menu")["slots"]
            if entry["slot"] in (100, 101, 102, 103, 200)}


def output(control, count):
    def has_result():
        value = grid(control).get(200)
        return value is not None and value["item"] == SCHEDULE and value["count"] == count
    MULTIPLAYER["until"](f"the {count}-schedule result", has_result)
    return grid(control)[200]


def no_result(control):
    control.call("wait", 4)
    if grid(control).get(200) is not None:
        raise RuntimeError("An invalid copy layout produced a crafting result.")


def place(control, source, destination):
    control.call("click-slot", source)
    control.call("click-slot", destination)


def preview_fields(stack):
    if stack.get("custom_name") != "Route Master" or stack.get("enchantments") or stack.get("stored_enchantments"):
        raise RuntimeError(f"The copy preview changed its name or retained enchantments: {stack}")


def copy_fields(stack, original, schedule):
    data = components(stack)
    actual = (data.get(COMPONENT) == schedule, data.get("minecraft:custom_name") == original.get("minecraft:custom_name"),
              "minecraft:enchantments" not in data and "minecraft:stored_enchantments" not in data)
    if actual != (True, True, True):
        raise RuntimeError(f"The result changed the Java schedule, custom name, or enchantments: {stack}")


def exercise(control, expected, schedule):
    MULTIPLAYER["until"]("both Schedule inputs", lambda: all(
        hotbar(control, slot).get("item") == SCHEDULE for slot in (0, 3)
    ))
    for slot in (0, 3):
        control.call("key", str(slot + 1), "tap")
        control.call("wait", 2)
        ENTRY["enter_and_close"](control, schedule)
        MULTIPLAYER["until"]("the programmed input", lambda: components(hotbar(control, slot)).get(COMPONENT) == schedule)
    control.call("key", "1", "tap")
    original = components(hotbar(control, 0))
    if original.get(COMPONENT) != schedule or original.get("minecraft:custom_name") is None:
        raise RuntimeError(f"Could not seed the named reference Schedule: {original}")
    if not all(original.get(key) for key in ("minecraft:enchantments", "minecraft:stored_enchantments")):
        raise RuntimeError(f"Could not seed both Java enchantment components: {original}")
    control.call("open-inventory")
    place(control, 1, 101)
    blank = output(control, expected["single_blank_reset_result"])
    if blank.get("custom_name") or components(blank).get(COMPONENT):
        raise RuntimeError(f"Reset of a single blank Schedule slot yielded {blank}.")
    place(control, 0, 100)
    count = expected["results"][0]
    preview_fields(output(control, count))

    control.call("click-slot", 101)
    control.call("click-slot", 101, "right")
    control.call("click-slot", 102, "right")
    control.call("click-slot", 1)
    count = expected["results"][1]
    preview_fields(output(control, count))

    place(control, 2, 103)
    no_result(control)
    place(control, 103, 2)
    place(control, 3, 103)
    no_result(control)
    place(control, 103, 3)
    output(control, count)

    place(control, 200, 0)
    owned = hotbar(control, 0)
    if owned.get("count") != expected["taken_count"] or hotbar(control, 1).get("count") != expected["leftover_blanks"]:
        raise RuntimeError("Taking the result consumed or duplicated an input stack.")
    if any(grid(control).get(slot) is not None for slot in (100, 101, 102, 103, 200)):
        raise RuntimeError("The used copy ingredients remained on the crafting grid.")
    copy_fields(owned, original, schedule)
    control.call("close")


def run(args):
    expected = json.loads((ROOT / "fixtures/train-schedule-copy-java.json").read_text())
    schedule = json.loads((ROOT / "fixtures/train-schedule-entry-java.json").read_text())
    with fixture_world(args, "train-schedule-copy", render=True, pack=args.pack) as host:
        host.commands((
            "/fill 5 95 37 12 95 46 minecraft:smooth_stone",
            "/tp @s 8.5 96 43.3 180 -30",
            "/gamemode survival",
        ))
        setup(host, "@s")
        exercise(host, expected, schedule)
        network = host.call("lan", "open", "0", "commands", "force")
        with TemporaryDirectory(prefix="hc-copy-lan-") as scratch, MULTIPLAYER["joined_client"](
            args, Path(scratch), f"127.0.0.1:{network['port']}", GUEST, render=True,
            scenario="train-schedule-copy", pack=args.pack,
        ) as guest:
            MULTIPLAYER["until"]("the copy guest to enter", lambda: any(
                player["name"] == GUEST and player["placed"] for player in host.call("lan", "status")["guests"]
            ))
            host.commands((f"/tp {GUEST} 9.5 96 43.3 180 -30", f"/gamemode survival {GUEST}"))
            setup(host, GUEST)
            exercise(guest, expected, schedule)
            if ENTRY["selected_schedule"](host, GUEST) != schedule:
                raise RuntimeError("The guest copied schedule was absent from the host's inventory state.")
    print("Survival host and guest matched Java's Schedule copy counts, component preservation, enchantment removal and rejected input layouts.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda p: Path(p).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    run(parser.parse_args())
