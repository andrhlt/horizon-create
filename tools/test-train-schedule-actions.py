#!/usr/bin/env python3
"""Choose and reopen original Schedule actions in host and LAN UI."""
import argparse
import json
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from fixture_world import ROOT, fixture_world

entry = import_module("test-train-schedule-entry")
delay = import_module("test-train-schedule-delay")
multiplayer = import_module("test-multiplayer")
GUEST = "ScheduleAction"

def exercise(world, actor, who, expected):
    delay.prepare_item(world, actor, who)
    entry.use(actor)
    actor.call("click-button", "Add Action")
    delay.scroll(actor, "Next Action:", -1, 3)
    actor.call("click-button", "Schedule Title")
    actor.call("type", "Night Express")
    actor.call("click-button", "Confirm Action")
    if not entry.buttons(actor)["Night Express"]["enabled"]:
        raise RuntimeError("The title action card did not show the entered name.")
    actor.call("click-button", "Done")
    actor.call("wait", 7)
    delay.check_saved(world, actor, who, expected["title"])

    entry.use(actor)
    actor.call("click-button", "Night Express")
    if "Schedule Title" not in entry.buttons(actor):
        raise RuntimeError("The selected title action did not reopen.")
    delay.scroll(actor, "Next Action:", -1)
    delay.scroll(actor, "Throttle", -1, 5)
    actor.call("click-button", "Confirm Action")
    if not entry.buttons(actor)["75%"]["enabled"]:
        raise RuntimeError("The throttle card did not show the original 75% value.")
    actor.call("click-button", "Done")
    actor.call("wait", 7)
    delay.check_saved(world, actor, who, expected["throttle"])

    entry.use(actor)
    actor.call("click-button", "75%")
    if "Throttle" not in entry.buttons(actor):
        raise RuntimeError("The selected throttle action did not reopen.")
    actor.call("click-button", "Confirm Action")
    actor.call("click-button", "Done")
    actor.call("wait", 7)
    delay.check_saved(world, actor, who, expected["throttle"])


def exercise_packages(world, actor, who, expected):
    address_label = "Retrieve Packages with this Address"
    delay.prepare_item(world, actor, who)
    entry.use(actor)
    actor.call("click-button", "Add Action")
    delay.scroll(actor, "Next Action:", -1)
    if "Station Name" in entry.buttons(actor) or address_label in entry.buttons(actor):
        raise RuntimeError("Deliver Package exposed an unrelated text field.")
    actor.call("click-button", "Confirm Action")
    actor.call("click-button", "Wait: 5s")
    delay.scroll(actor, "Duration", 1, 2)
    actor.call("click-button", "Confirm Condition")
    actor.call("click-button", "Done")
    actor.call("wait", 8)
    delay.check_saved(world, actor, who, expected["deliver"])

    entry.use(actor)
    actor.call("click-button", "Deliver Package")
    delay.scroll(actor, "Next Action:", -1)
    actor.call("click-button", address_label)
    actor.call("type", "Warehouse ****")
    actor.call("click-button", "Confirm Action")
    actor.call("click-button", "Done")
    actor.call("wait", 8)
    delay.check_saved(world, actor, who, expected["retrieve"])

    entry.use(actor)
    if not entry.buttons(actor)["Wait: 7s"]["enabled"]:
        raise RuntimeError("The edited wait disappeared from the Retrieve Package row.")
    actor.call("click-button", "Retrieve Package")
    if address_label not in entry.buttons(actor):
        raise RuntimeError("The saved package address editor did not reopen.")
    actor.call("click-button", "Confirm Action")
    actor.call("click-button", "Done")
    actor.call("wait", 8)
    delay.check_saved(world, actor, who, expected["retrieve"])


def run(args):
    name = "train-schedule-package-editor" if args.packages else "train-schedule-actions"
    fixture = "train-schedule-package-editor-java.json" if args.packages else "train-schedule-action-java.json"
    expected = json.loads((ROOT / "fixtures" / fixture).read_text())
    replay = exercise_packages if args.packages else exercise
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
        with TemporaryDirectory(prefix="hc-action-") as scratch, multiplayer.joined_client(
            args, Path(scratch), f"127.0.0.1:{port}", GUEST,
            render=True, scenario=name, pack=args.pack,
        ) as guest:
            multiplayer.until("the action editor guest", lambda: any(
                link["name"] == GUEST and link["placed"] for link in world.call("lan", "status")["guests"]
            ))
            world.commands((f"/gamemode survival {GUEST}", f"/tp {GUEST} 10.5 96 41.3 -90 -25"))
            guest.call("wait", 4)
            replay(world, guest, GUEST, expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--multiplayer", action="store_true")
    parser.add_argument("--packages", action="store_true")
    for arg in ("ctl", "client", "resources"):
        parser.add_argument(arg, type=lambda path: Path(path).resolve(strict=True))
    args = parser.parse_args()
    run(args)
    actions = "Deliver and Retrieve Package" if args.packages else "Schedule Title and Limit Max Speed"
    print(f"{actions} edits saved and reopened exact original Java action data.")
