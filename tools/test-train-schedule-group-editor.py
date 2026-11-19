#!/usr/bin/env python3
"""Edit sequential and alternative waits through the original Schedule controls."""
import argparse
import json
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

entry = import_module("test-train-schedule-entry")
delay = import_module("test-train-schedule-delay")
multiplayer = import_module("test-multiplayer")
GUEST = "ScheduleGroups"


def create_delay(actor, label, value):
    actor.call("click-button", label)
    delay.scroll(actor, "Duration", 1, value - 5)
    delay.scroll(actor, "Time Unit", 1)
    actor.call("click-button", "Confirm Condition")
    actor.call("wait", 3)


def close(actor):
    actor.call("click-button", "Done")
    actor.call("wait", 8)


def remove(actor, name):
    bounds = entry.buttons(actor)[name]
    actor.call("click-at", int(bounds["x"] + bounds["w"] / 2), int(bounds["y"] + bounds["h"] / 2), "right")
    actor.call("wait", 3)
    if name in entry.buttons(actor):
        raise RuntimeError(f"Right-click left {name} in the Schedule.")


def exercise(world, actor, who, expected):
    delay.prepare_item(world, actor, who)
    entry.enter_and_close(actor, expected["removed_alt"])
    delay.check_saved(world, actor, who, expected["removed_alt"])

    entry.use(actor)
    create_delay(actor, "Add Condition", 6)
    create_delay(actor, "Alternative Condition", 8)
    if not {"Wait: 5s", "Wait: 6t", "Wait: 8t"}.issubset(entry.buttons(actor)):
        raise RuntimeError("Sequential and alternative rows are not visible in the timetable.")
    close(actor)
    delay.check_saved(world, actor, who, expected["groups"])

    entry.use(actor)
    remove(actor, "Wait: 6t")
    close(actor)
    delay.check_saved(world, actor, who, expected["removed_term"])

    entry.use(actor)
    remove(actor, "Wait: 8t")
    close(actor)
    delay.check_saved(world, actor, who, expected["removed_alt"])

    entry.use(actor)
    bounds = entry.buttons(actor)["Wait: 5s"]
    actor.call("click-at", int(bounds["x"] + bounds["w"] / 2), int(bounds["y"] + bounds["h"] / 2), "right")
    if "Wait: 5s" not in entry.buttons(actor):
        raise RuntimeError("A sole mandatory condition should not be removed.")
    close(actor)
    delay.check_saved(world, actor, who, expected["removed_alt"])


def run(args):
    expected=json.loads((ROOT / "fixtures/train-schedule-group-editor-java.json").read_text())
    name = "train-schedule-group-editor-lan" if args.multiplayer else "train-schedule-group-editor"
    with fixture_world(args, name, render=True, pack=args.pack) as world:
        world.commands((
            "/fill 4 95 36 15 95 46 minecraft:smooth_stone",
            "/tp @s 8.5 96 41.3 -90 -25",
            "/gamemode survival",
        ))
        if not args.multiplayer:
            exercise(world, world, "@s", expected)
            return
        port = world.call("lan", "open", "0", "commands", "force")["port"]
        with TemporaryDirectory(prefix="hc-group-editor-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST,
            render=True, scenario=name, pack=args.pack,
        ) as guest:
            multiplayer.until("the group editor guest", lambda: any(
                link["name"] == GUEST and link["placed"] for link in world.call("lan", "status")["guests"]
            ))
            world.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} 10.5 96 41.3 -90 -25"))
            guest.call("wait", 4)
            exercise(world, guest, GUEST, expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    run(parser.parse_args())
    print("Appended, alternative, and right-click removed Schedule conditions matched exact Java components.")
