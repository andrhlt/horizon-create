#!/usr/bin/env python3
"""Author and reopen waiting conditions through the real Schedule UI."""
import argparse
import json
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

entry = import_module("test-train-schedule-entry")
delay = import_module("test-train-schedule-delay")
multiplayer = import_module("test-multiplayer")
GUEST = "ConditionGuest"
TIME_LABEL = "10:20 am"


def confirm(actor, label):
    actor.call("click-button", "Confirm Condition")
    if not entry.buttons(actor)[label]["enabled"]:
        raise RuntimeError(f"The selected wait is not visible: {label}")
    actor.call("click-button", "Done")
    actor.call("wait", 8)


def exercise(world, actor, who, expected):
    delay.prepare_item(world, actor, who)
    entry.enter_and_close(actor, expected["initial"])
    delay.check_saved(world, actor, who, expected["initial"])

    entry.use(actor)
    actor.call("click-button", "Wait: 5s")
    delay.scroll(actor, "Continue if/after:", -1)
    delay.scroll(actor, "Hour", 1, 2)
    delay.scroll(actor, "Minute", 1, 20)
    delay.scroll(actor, "Rotation", -1)
    confirm(actor, TIME_LABEL)
    delay.check_saved(world, actor, who, expected["time"])

    entry.use(actor)
    actor.call("click-button", TIME_LABEL)
    if not {"Hour", "Minute", "Rotation"}.issubset(entry.buttons(actor)):
        raise RuntimeError("The Time of Day settings did not reopen on the item.")
    delay.scroll(actor, "Continue if/after:", -1, 7)
    confirm(actor, "Station Powered")
    delay.check_saved(world, actor, who, expected["power"])

    entry.use(actor)
    actor.call("click-button", "Station Powered")
    if "Hour" in entry.buttons(actor) or "Duration" in entry.buttons(actor):
        raise RuntimeError("Station Powered exposed an unrelated input.")
    confirm(actor, "Station Powered")
    delay.check_saved(world, actor, who, expected["power"])


def exercise_unloaded(world, actor, who, expected):
    delay.prepare_item(world, actor, who)
    entry.enter_and_close(actor, expected["initial"])
    entry.use(actor)
    actor.call("click-button", "Wait: 5s")
    delay.scroll(actor, "Continue if/after:", -1, 7)
    for reopen in (False, True):
        if reopen:
            entry.use(actor)
            actor.call("click-button", "Chunk Unloaded")
        if {"Hour", "Duration", "Players", "Frequency #1"}.intersection(entry.buttons(actor)):
            raise RuntimeError("Chunk Unloaded exposed an unrelated parameter.")
        confirm(actor, "Chunk Unloaded")
        delay.check_saved(world, actor, who, expected["unloaded"])


def exercise_idle(world, actor, who, expected):
    delay.prepare_item(world, actor, who)
    entry.enter_and_close(actor, expected["initial"])
    entry.use(actor)
    actor.call("click-button", "Wait: 5s")
    delay.scroll(actor, "Continue if/after:", -1, 6)
    confirm(actor, "Cargo Idle: 5s")
    delay.check_saved(world, actor, who, expected["idle"]["default"])

    entry.use(actor)
    actor.call("click-button", "Cargo Idle: 5s")
    delay.scroll(actor, "Duration", 1, 3)
    delay.scroll(actor, "Time Unit", 1)
    confirm(actor, "Cargo Idle: 8t")
    delay.check_saved(world, actor, who, expected["idle"]["edited"])

    entry.use(actor)
    actor.call("click-button", "Cargo Idle: 8t")
    if not {"Duration", "Time Unit"}.issubset(entry.buttons(actor)):
        raise RuntimeError("Cargo Inactivity duration controls did not reopen.")
    confirm(actor, "Cargo Idle: 8t")
    delay.check_saved(world, actor, who, expected["idle"]["edited"])


def run(args):
    expected = json.loads((ROOT / "fixtures/train-schedule-condition-types-java.json").read_text())
    name = "train-schedule-conditions"
    replay = exercise
    if args.unloaded:
        name = "train-schedule-unloaded-editor"
        expected["unloaded"] = json.loads((ROOT / "fixtures/train-schedule-unloaded-editor-java.json").read_text())
        replay = exercise_unloaded
    elif args.idle:
        name = "train-schedule-idle-editor"
        expected["idle"] = json.loads((ROOT / "fixtures/train-schedule-idle-editor-java.json").read_text())
        replay = exercise_idle
    if args.multiplayer:
        name += "-lan"
    with fixture_world(args, name, render=True, pack=args.pack) as world:
        world.commands((
            "/fill 4 95 36 15 95 46 minecraft:smooth_stone",
            "/tp @s 8.5 96 41.3 -90 -25",
            "/gamemode survival",
        ))
        if not args.multiplayer:
            replay(world, world, "@s", expected)
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-condition-editor-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST,
            render=True, scenario=name, pack=args.pack,
        ) as guest:
            multiplayer.until("the condition editor guest", lambda: any(
                link["name"] == GUEST and link["placed"] for link in world.call("lan", "status")["guests"]
            ))
            world.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} 10.5 96 41.3 -90 -25"))
            guest.call("wait", 4)
            replay(world, guest, GUEST, expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    kind = parser.add_mutually_exclusive_group()
    kind.add_argument("--unloaded", action="store_true")
    kind.add_argument("--idle", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    args = parser.parse_args()
    run(args)
    if args.unloaded:
        checked = "Chunk Unloaded"
    elif args.idle:
        checked = "Cargo Inactivity"
    else:
        checked = "Time of Day and Station Powered"
    print(f"{checked} condition edits matched Java after save and reopen.")
