#!/usr/bin/env python3
"""Move and duplicate real Schedule rows without changing their timed actions."""
import argparse
import json
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

entry = import_module("test-train-schedule-entry")
delay = import_module("test-train-schedule-delay")
conductor = import_module("test-train-conductor")
multiplayer = conductor.multiplayer
GUEST = "ScheduleSorter"


def exercise(world, actor, who, expected):
    delay.prepare_item(world, actor, who)
    starting = json.dumps(expected["start"], separators=(",", ":")).replace('"Cyclic":0', '"Cyclic":0b')
    conductor.set_held(world, actor, who, conductor.SCHEDULE,
                       components='{"create:train_schedule":' + starting + "}")
    delay.check_saved(world, actor, who, expected["start"])

    for label, state in (("Move up 2", "up"), ("Duplicate 2", "duplicated"), ("Move down 1", "down")):
        entry.use(actor)
        actor.call("click-button", label)
        actor.call("wait", 3)
        actor.call("click-button", "Done")
        actor.call("wait", 8)
        delay.check_saved(world, actor, who, expected[state])

    entry.use(actor)
    buttons = entry.buttons(actor)
    if not buttons["Reset Progress"]["enabled"] or not buttons["Duplicate 2"]["enabled"]:
        raise RuntimeError("The reordered Schedule did not reopen with its progress and actions.")


def run(args):
    expected=json.loads((ROOT / "fixtures/train-schedule-row-actions-java.json").read_text())
    name = "train-schedule-row-actions-lan" if args.multiplayer else "train-schedule-row-actions"
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
        with TemporaryDirectory(prefix="hc-row-actions-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST,
            render=True, scenario=name, pack=args.pack,
        ) as guest:
            multiplayer.until("the Schedule sorter guest", lambda: any(
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
    print("Schedule move-up, duplicate, and move-down kept the exact Java component and progress.")
